"""
GUI for the servo-output assignment plugin.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import Frame, ttk
from tkinter.messagebox import showerror, showinfo

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.plugins.data_model_servo_out import ServoOutDataModel
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_SERVO_OUT
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory


class ServoOutView(Frame):
    """Show and apply safe default motor-function assignments."""

    def __init__(self, parent: tk.Frame | ttk.Frame, model: ServoOutDataModel, base_window: BaseWindow) -> None:
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        self._summary = tk.StringVar(value="")
        ttk.Label(self, text=_("Servo Output Functions"), font=("TkDefaultFont", 14, "bold")).pack(pady=(0, 8))
        ttk.Label(
            self,
            text=_(
                "Use the FC-to-ESC connection type and FRAME_CLASS to propose motor outputs. "
                "Existing non-zero function assignments are preserved."
            ),
            justify="left",
            wraplength=600,
        ).pack(pady=(0, 8))
        ttk.Label(self, textvariable=self._summary, justify="left", wraplength=600).pack(pady=(0, 8))
        ttk.Button(self, text=_("Apply Recommended Motor Outputs"), command=self._on_apply).pack(pady=8)
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        recommendations, message = self.model.get_recommendations()
        if recommendations:
            assignments = ", ".join(f"{name}={value}" for name, value in recommendations.items())
            self._summary.set(f"{message}\n{assignments}")
        else:
            self._summary.set(message)

    def _on_apply(self) -> None:
        applied, message = self.model.apply_recommendations()
        if applied:
            showinfo(_("Servo Output Functions"), message)
        else:
            showerror(_("Servo Output Functions"), message)
        self._refresh_summary()


def _create_servo_out_view(parent: tk.Frame | ttk.Frame, model: object, base_window: object) -> ServoOutView:
    """Create the servo-output view for the plugin factory."""
    return ServoOutView(parent, model, base_window)  # type: ignore[arg-type]


def _create_servo_out_model(context: PluginModelContext) -> ServoOutDataModel:
    """Create the servo-output data model from application dependencies."""
    return ServoOutDataModel(context.local_filesystem, context.parameter_editor)


def register_servo_out_plugin() -> None:
    """Register the servo-output plugin with the factory."""
    plugin_factory.register(PLUGIN_SERVO_OUT, _create_servo_out_view, _create_servo_out_model)
