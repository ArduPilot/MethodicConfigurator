"""
GUI for the level calibration plugin.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from contextlib import suppress
from sys import platform as sys_platform
from threading import Event, Thread
from tkinter import Frame, ttk
from tkinter.messagebox import showerror, showinfo, showwarning

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_progress_window import ProgressWindow
from ardupilot_methodic_configurator.plugins.data_model_level_calibration import LevelCalibrationDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_helpers import apply_calibration_readback
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_LEVEL_CALIBRATION
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory

_CALIBRATION_POLL_INTERVAL_MS = 50


class LevelCalibrationView(Frame):  # pylint: disable=too-many-instance-attributes
    """Allow the user to level-trim a calibrated vehicle."""

    def __init__(self, parent: tk.Frame | ttk.Frame, model: LevelCalibrationDataModel, base_window: BaseWindow) -> None:
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        self._calibration_thread: Thread | None = None
        self._calibration_poll_job: str | None = None
        self._calibration_result: tuple[bool, str] | None = None
        self._calibration_error: Exception | None = None
        self._calibration_readback_error: str | None = None
        self._calibration_progress_window: ProgressWindow | None = None
        self._calibration_cancelled = Event()
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
        self._calibration_readback_error = None
        self._calibration_cancelled.clear()

        def run_calibration() -> None:
            try:
                self._calibration_result = self.model.start_level_calibration()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self._calibration_error = exc
                return

            if self._calibration_result[0] and not self._calibration_cancelled.is_set():
                self._read_back_calibrated_parameters()

        try:
            self.base_window.set_fc_operation_busy(busy=True)
            self._show_calibration_progress()
            self._calibration_thread = Thread(target=run_calibration, daemon=True)
            self._calibration_thread.start()
            self._calibration_poll_job = self.after(_CALIBRATION_POLL_INTERVAL_MS, self._poll_level_calibration)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._close_calibration_progress()
            self._level_btn.configure(state="normal")
            showerror(_("Calibration Failed"), str(exc) or repr(exc))

    def _show_calibration_progress(self) -> None:
        """Show a modal progress indicator while the shared MAVLink link is in use."""
        self._calibration_progress_window = ProgressWindow(
            self.base_window.root,
            _("Level Calibration"),
            _("Calibrating the vehicle and reading back parameters..."),
        )
        self._calibration_progress_window.progress_bar.configure(mode="indeterminate")
        self._calibration_progress_window.progress_bar.start(10)
        self._calibration_progress_window.progress_window.protocol("WM_DELETE_WINDOW", lambda: None)
        if sys_platform != "darwin":
            self._calibration_progress_window.progress_window.grab_set()

    def _close_calibration_progress(self) -> None:
        """Release the modal UI lock and remove the calibration progress indicator."""
        progress_window = self._calibration_progress_window
        self._calibration_progress_window = None
        if progress_window is not None:
            with suppress(tk.TclError):
                progress_window.progress_bar.stop()
                if sys_platform != "darwin":
                    progress_window.progress_window.grab_release()
            progress_window.destroy()
        self.base_window.set_fc_operation_busy(busy=False)

    def _read_back_calibrated_parameters(self) -> None:
        """Read the calibration output without mutating Tk-owned state from the worker."""
        parameter_editor = getattr(self.base_window, "parameter_editor", None)
        download_parameters = getattr(parameter_editor, "download_flight_controller_parameters", None)
        if not callable(download_parameters):
            self._calibration_readback_error = _("Could not read calibrated parameters from the flight controller.")
            return
        try:
            # The active step is a Tk-owned object.  Refresh it only after the
            # worker is complete and the UI thread has verified this readback.
            fc_parameters, _defaults = download_parameters(update_current_step_fc_values=False)
            if not fc_parameters:
                self._calibration_readback_error = _("Could not read calibrated parameters from the flight controller.")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._calibration_readback_error = str(exc) or repr(exc)

    def _poll_level_calibration(self) -> None:
        """Finish the background calibration on the Tk main thread."""
        self._calibration_poll_job = None
        if self._calibration_thread is not None and self._calibration_thread.is_alive():
            self._calibration_poll_job = self.after(_CALIBRATION_POLL_INTERVAL_MS, self._poll_level_calibration)
            return

        self._level_btn.configure(state="normal")
        self._close_calibration_progress()
        if self._calibration_error is not None:
            showerror(_("Calibration Failed"), str(self._calibration_error) or repr(self._calibration_error))
            return

        result = self._calibration_result
        if result is None:
            showerror(_("Calibration Failed"), _("Level calibration failed"))
            return

        success, message = result
        # pylint: disable=duplicate-code
        if success:
            if self._calibration_readback_error is None:
                apply_calibration_readback(
                    self.base_window,
                    parameter_names_to_copy={"AHRS_TRIM_X", "AHRS_TRIM_Y"},
                )
            showinfo(_("Calibration Result"), message)
            if self._calibration_readback_error is not None:
                showwarning(_("Calibration Readback Failed"), self._calibration_readback_error)
        else:
            showerror(_("Calibration Failed"), message)
        # pylint: enable=duplicate-code

    def destroy(self) -> None:
        """Cancel pending polling before destroying the view."""
        if self._calibration_poll_job is not None:
            self.after_cancel(self._calibration_poll_job)
            self._calibration_poll_job = None
        self._calibration_cancelled.set()
        self._close_calibration_progress()
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
