"""
GUI for compass calibration plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import messagebox, ttk

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_compass_calibration import CompassCalibrationDataModel
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.plugin_constants import PLUGIN_COMPASS_CALIBRATION
from ardupilot_methodic_configurator.plugin_factory import plugin_factory


class CompassCalibrationView(ttk.Frame):  # pylint: disable=too-many-ancestors
    """GUI for compass calibration plugin."""

    def __init__(
        self,
        parent: tk.Frame | ttk.Frame,
        model: CompassCalibrationDataModel,
        base_window: BaseWindow,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        self._timer_id: str | None = None

        self.start_button: ttk.Button
        self.cancel_button: ttk.Button
        self.progress_bar: ttk.Progressbar

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        title_label = ttk.Label(
            main_frame,
            text=_("Compass Calibration"),
            font=("TkDefaultFont", 14, "bold"),
        )
        title_label.pack(pady=(0, 15))

        # Instructions
        info_text = _(
            "1. Click 'Start Calibration'.\n"
            "2. Hold the vehicle in the air and rotate it so that each side\n"
            "   (front, back, left, right, top, and bottom) points down towards the earth.\n"
            "3. Hold each position for a few seconds until the bar progresses.\n"
            "4. Continue rotating until the progress bar reaches 100%."
        )
        instructions_label = ttk.Label(main_frame, text=info_text, justify="left")
        instructions_label.pack(pady=(0, 20))

        # Progress Bar
        self.progress_bar = ttk.Progressbar(main_frame, orient="horizontal", length=400, mode="determinate")
        self.progress_bar.pack(pady=20)

        # Buttons Frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=10)

        self.start_button = ttk.Button(buttons_frame, text=_("Start Calibration"), command=self._on_start)
        self.start_button.pack(side="left", padx=10)

        self.cancel_button = ttk.Button(buttons_frame, text=_("Cancel"), command=self._on_cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=10)

    def _on_start(self) -> None:
        """Handle start button click."""
        success, error_msg = self.model.start_calibration()
        if success:
            self.start_button.config(state="disabled")
            self.cancel_button.config(state="normal")
            self.progress_bar["value"] = 0
            # Tkinter timer at 10Hz
            self._timer_id = self.after(100, self._check_progress)
        else:
            messagebox.showerror(_("Failed to Start"), error_msg)

    def _on_cancel(self) -> None:
        """Handle cancel button click."""
        success, error_msg = self.model.cancel_calibration()
        if success:
            self._reset_ui()
            messagebox.showinfo(_("Cancelled"), _("Compass calibration was cancelled."))
        else:
            messagebox.showerror(_("Failed to Cancel"), error_msg)

    def _reset_ui(self) -> None:
        """Reset the UI elements and kill the timer."""
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None
        self.start_button.config(state="normal")
        self.cancel_button.config(state="disabled")
        self.progress_bar["value"] = 0

    def _check_progress(self) -> None:
        """Periodic update callback for calibration progress."""
        data = self.model.get_progress()

        if data is None:
            # Keep waiting for data to arrive in the MAVLink stream
            self._timer_id = self.after(100, self._check_progress)
            return

        if data["type"] == "PROGRESS":
            pct = data.get("completion_pct", 0)
            self.progress_bar["value"] = int(pct)

            self._timer_id = self.after(100, self._check_progress)

        elif data["type"] == "REPORT":
            self._reset_ui()
            status = data.get("status")

            # MAVLink enum CompassCalibrator::Status
            if data.get("saved") or status == 4:
                messagebox.showinfo(_("Calibration Complete"), _("Compass successfully calibrated and saved!"))
            else:
                messagebox.showerror(
                    _("Calibration Failed"),
                    _("Calibration failed. Please try again in an area with less magnetic interference."),
                )

    def on_activate(self) -> None:
        """Called when the plugin becomes active."""
        self._reset_ui()

    def on_deactivate(self) -> None:
        """Called when the plugin becomes inactive."""
        if self._timer_id:
            self.model.cancel_calibration()
            self._reset_ui()

    def destroy(self) -> None:
        """Clean up the plugin and release resources."""
        if self._timer_id:
            self.model.cancel_calibration()
            self._reset_ui()
        super().destroy()


# plugins and registration
def _create_compass_calibration_view(
    parent: tk.Frame | ttk.Frame,
    model: object,
    base_window: object,
) -> CompassCalibrationView:
    return CompassCalibrationView(parent, model, base_window)  # type: ignore[arg-type]


def register_compass_calibration_plugin() -> None:
    """Register the compass calibration plugin with the factory."""
    plugin_factory.register(PLUGIN_COMPASS_CALIBRATION, _create_compass_calibration_view)
