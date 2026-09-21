"""
GUI for the level calibration plugin.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from threading import Thread
from tkinter import Frame, ttk
from tkinter.messagebox import showerror, showinfo

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.plugins.data_model_level_calibration import LevelCalibrationDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_helpers import refresh_parameter_editor_after_calibration
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_LEVEL_CALIBRATION
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory

_CALIBRATION_POLL_INTERVAL_MS = 50


class LevelCalibrationView(Frame):
    """Allow the user to level-trim a calibrated vehicle."""

    def __init__(self, parent: tk.Frame | ttk.Frame, model: LevelCalibrationDataModel, base_window: BaseWindow) -> None:
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        self._calibration_thread: Thread | None = None
        self._calibration_poll_job: str | None = None
        self._calibration_result: tuple[bool, str] | None = None
        self._calibration_error: Exception | None = None
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
                "Must be performed AFTER a Simple or Full calibration. "
                "Place the calibrated vehicle on a level surface and keep it still. "
                "This trims roll and pitch only; it does not affect yaw."
            ),
            justify="left",
            wraplength=600,
        )
        self._level_info_label.pack(side="left", fill="x", expand=True, anchor="w")

    def _on_level_calibration(self) -> None:
        if self._calibration_thread is not None and self._calibration_thread.is_alive():
            return

        self._level_btn.configure(state="disabled")
        self._calibration_result = None
        self._calibration_error = None

        def run_calibration() -> None:
            try:
                self._calibration_result = self.model.start_level_calibration()
                if self._calibration_result[0]:
                    parameter_editor = getattr(self.base_window, "parameter_editor", None)
                    download_parameters = getattr(parameter_editor, "download_flight_controller_parameters", None)
                    if callable(download_parameters):
                        # Do not touch the active step from this worker: the user may
                        # navigate while the FC parameter readback is in progress.
                        download_parameters(update_current_step_fc_values=False)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self._calibration_error = exc

        self._calibration_thread = Thread(target=run_calibration, daemon=True)
        self._calibration_thread.start()
        self._calibration_poll_job = self.after(_CALIBRATION_POLL_INTERVAL_MS, self._poll_level_calibration)

    def _poll_level_calibration(self) -> None:
        """Finish the background calibration on the Tk main thread."""
        self._calibration_poll_job = None
        if self._calibration_thread is not None and self._calibration_thread.is_alive():
            self._calibration_poll_job = self.after(_CALIBRATION_POLL_INTERVAL_MS, self._poll_level_calibration)
            return

        self._level_btn.configure(state="normal")
        if self._calibration_error is not None:
            showerror(_("Calibration Failed"), str(self._calibration_error))
            return

        result = self._calibration_result
        if result is None:
            showerror(_("Calibration Failed"), _("Level calibration failed"))
            return

        success, message = result
        # pylint: disable=duplicate-code
        if success:
            refresh_parameter_editor_after_calibration(
                self.base_window,
                parameter_names_to_copy={"AHRS_TRIM_X", "AHRS_TRIM_Y"},
                download=False,
            )
            showinfo(_("Calibration Result"), message)
        else:
            showerror(_("Calibration Failed"), message)
        # pylint: enable=duplicate-code

    def destroy(self) -> None:
        """Cancel pending polling before destroying the view."""
        if self._calibration_poll_job is not None:
            self.after_cancel(self._calibration_poll_job)
            self._calibration_poll_job = None
        super().destroy()


def _create_level_calibration_view(parent: tk.Frame | ttk.Frame, model: object, base_window: object) -> LevelCalibrationView:
    """Create the level-calibration view for the plugin factory."""
    return LevelCalibrationView(parent, model, base_window)  # type: ignore[arg-type]


def _create_level_calibration_model(context: PluginModelContext) -> LevelCalibrationDataModel:
    """Create the level-calibration data model from application dependencies."""
    return LevelCalibrationDataModel(context.flight_controller)


def register_level_calibration_plugin() -> None:
    """Register the level calibration plugin with the factory."""
    plugin_factory.register(PLUGIN_LEVEL_CALIBRATION, _create_level_calibration_view, _create_level_calibration_model)
