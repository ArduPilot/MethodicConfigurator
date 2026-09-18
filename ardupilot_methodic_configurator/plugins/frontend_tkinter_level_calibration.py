"""
GUI for the level calibration plugin.

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
from ardupilot_methodic_configurator.plugins.data_model_level_calibration import LevelCalibrationDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_helpers import refresh_parameter_editor_after_calibration
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_LEVEL_CALIBRATION
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory


class LevelCalibrationView(Frame):
    """Allow the user to level-trim a calibrated vehicle."""

    def __init__(self, parent: tk.Frame | ttk.Frame, model: LevelCalibrationDataModel, base_window: BaseWindow) -> None:
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True)

        ttk.Label(
            main_frame,
            text=_("Accelerometer Level Calibration"),
            font=("TkDefaultFont", 14, "bold"),
        ).pack(pady=(0, 10))

        calibration_frame = ttk.Frame(main_frame)
        calibration_frame.pack(fill="x", pady=(0, 10))

        self._level_btn = ttk.Button(
            calibration_frame,
            text=_("Level Calibration (Trim)"),
            command=self._on_level_calibration,
        )
        self._level_btn.pack(side="left", padx=(8, 16), anchor="n")

        self._level_info_label = ttk.Label(
            calibration_frame,
            text=_(
                "Place the calibrated vehicle on a level surface and keep it still. "
                "This trims roll and pitch only; it does not affect yaw."
            ),
            justify="left",
            wraplength=600,
        )
        self._level_info_label.pack(side="left", fill="x", expand=True, anchor="w")

    def _on_level_calibration(self) -> None:
        success, message = self.model.start_level_calibration()
        if success:
            refresh_parameter_editor_after_calibration(self.base_window)
            showinfo(_("Calibration Result"), message)
        else:
            showerror(_("Calibration Failed"), message)


def _create_level_calibration_view(parent: tk.Frame | ttk.Frame, model: object, base_window: object) -> LevelCalibrationView:
    """Create the level-calibration view for the plugin factory."""
    return LevelCalibrationView(parent, model, base_window)  # type: ignore[arg-type]


def _create_level_calibration_model(context: PluginModelContext) -> LevelCalibrationDataModel:
    """Create the level-calibration data model from application dependencies."""
    return LevelCalibrationDataModel(context.flight_controller)


def register_level_calibration_plugin() -> None:
    """Register the level calibration plugin with the factory."""
    plugin_factory.register(PLUGIN_LEVEL_CALIBRATION, _create_level_calibration_view, _create_level_calibration_model)
