"""
GUI for accelerometer calibration plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 ArduPilot Contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import Frame, ttk
from tkinter.messagebox import showerror, showinfo

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_accelerometer_calibration import AccelerometerCalibrationDataModel
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.plugin_constants import PLUGIN_ACCELEROMETER_CALIBRATION
from ardupilot_methodic_configurator.plugin_factory import plugin_factory


class AccelerometerCalibrationView(Frame):
    """GUI for accelerometer calibration plugin."""

    def __init__(
        self,
        parent: tk.Frame | ttk.Frame,
        model: AccelerometerCalibrationDataModel,
        base_window: BaseWindow,
    ) -> None:
        """
        Initialize the accelerometer calibration view.

        Args:
            parent: Parent widget
            model: Data model for accelerometer calibration
            base_window: Parent BaseWindow instance

        """
        super().__init__(parent)
        self.model = model
        self.base_window = base_window

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True)

        # Title
        title_label = ttk.Label(
            main_frame,
            text=_("Accelerometer Calibration"),
            font=("TkDefaultFont", 14, "bold"),
        )
        title_label.pack(pady=(0, 20))

        # Info text
        info_text = _(
            "This tool calibrates the accelerometers without leaving the AMC interface.\n\n"
            "Simple calibration: Place vehicle level and click Simple Calibration.\n"
            "Full calibration: Follow on-screen instructions for 6 orientations."
        )
        info_label = ttk.Label(main_frame, text=info_text, justify="center")
        info_label.pack(pady=(0, 30))

        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(pady=20)

        simple_button = ttk.Button(
            buttons_frame,
            text=_("Simple Calibration (Level)"),
            command=self._on_simple_calibration,
        )
        simple_button.pack(side="left", padx=10)

        full_button = ttk.Button(
            buttons_frame,
            text=_("Full Calibration (6-Position)"),
            command=self._on_full_calibration,
        )
        full_button.pack(side="left", padx=10)

    def _on_simple_calibration(self) -> None:
        """Handle simple calibration button click."""
        success, message = self.model.start_simple_calibration()
        if success:
            showinfo(_("Calibration Started"), message)
        else:
            showerror(_("Calibration Failed"), message)

    def _on_full_calibration(self) -> None:
        """Handle full calibration button click."""
        success, message = self.model.start_full_calibration()
        if success:
            showinfo(_("Calibration Started"), message)
        else:
            showerror(_("Calibration Failed"), message)

    def on_activate(self) -> None:
        """Called when the plugin view is displayed (lifecycle method)."""

    def on_deactivate(self) -> None:
        """Called when the plugin view is hidden (lifecycle method)."""

    def destroy(self) -> None:
        """Cleanup resources when plugin is removed (lifecycle method)."""
        super().destroy()


def _create_accelerometer_calibration_view(
    parent: tk.Frame | ttk.Frame,
    model: object,
    base_window: object,
) -> AccelerometerCalibrationView:
    """
    Factory function to create AccelerometerCalibrationView instances.

    This function trusts that the caller provides the correct types
    as per the plugin protocol (duck typing approach).

    Args:
        parent: The parent frame
        model: The AccelerometerCalibrationDataModel instance (passed as object for protocol compliance)
        base_window: The BaseWindow instance (passed as object for protocol compliance)

    Returns:
        A new AccelerometerCalibrationView instance

    """
    # Trust the caller to provide correct types (protocol-based duck typing)
    # Type checker will verify this at static analysis time
    return AccelerometerCalibrationView(parent, model, base_window)  # type: ignore[arg-type]


def register_accelerometer_calibration_plugin() -> None:
    """Register the accelerometer calibration plugin with the factory."""
    plugin_factory.register(PLUGIN_ACCELEROMETER_CALIBRATION, _create_accelerometer_calibration_view)
