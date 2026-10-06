"""
GUI for the level calibration plugin.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from contextlib import suppress
from tkinter import Frame, ttk
from tkinter.messagebox import showerror, showinfo
from typing import Any, cast  # pylint: disable=unused-import

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.plugins.data_model_level_calibration import LevelCalibrationDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_helpers import (
    begin_calibration_navigation_lock,
    end_calibration_navigation_lock,
    refresh_parameter_editor_after_calibration,
)
from ardupilot_methodic_configurator.plugins.imu_helpers import stop_periodic_polling
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_LEVEL_CALIBRATION
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory

_LEVEL_CALIBRATION_POLL_INTERVAL_MS = 100


class LevelCalibrationView(Frame):
    """Allow the user to level-trim a calibrated vehicle."""

    def __init__(self, parent: tk.Frame | ttk.Frame, model: LevelCalibrationDataModel, base_window: BaseWindow) -> None:
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        self._calibration_in_progress = False
        self._poll_job: str | None = None
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
        if self._calibration_in_progress:
            return
        if not begin_calibration_navigation_lock(self.base_window, self):
            return
        self._calibration_in_progress = True
        self._level_btn.configure(state="disabled")
        started = False
        try:
            success, message = self.model.start_level_calibration()
            if not success:
                self._finish_level_calibration(success=False, message=message)
                return
            self._poll_job = self.after(_LEVEL_CALIBRATION_POLL_INTERVAL_MS, self._poll_level_calibration)
            started = True
        finally:
            if not started:
                self._restore_calibration_controls()

    def _poll_level_calibration(self) -> None:
        """Poll the backend once without blocking Tk's event loop."""
        try:
            self._check_level_calibration()
        except Exception:
            self._restore_calibration_controls()
            raise

    def _check_level_calibration(self) -> None:
        """Handle one asynchronous result with navigation still disabled."""
        self._poll_job = None
        if not self._calibration_in_progress:
            return
        result = self.model.poll_level_calibration()
        if result is None:
            self._poll_job = self.after(_LEVEL_CALIBRATION_POLL_INTERVAL_MS, self._poll_level_calibration)
            return
        self._finish_level_calibration(success=result[0], message=result[1], command_sent=True)

    def _finish_level_calibration(self, success: bool, message: str, *, command_sent: bool = False) -> None:
        """Restore controls and present the completed level-trim result."""
        try:
            self._present_level_calibration_result(success, message, command_sent=command_sent)
        finally:
            self._restore_calibration_controls()

    def _restore_calibration_controls(self) -> None:
        """Restore local controls without allowing widget teardown to strand the lock."""
        self._calibration_in_progress = False
        try:
            with suppress(tk.TclError):
                if self._level_btn.winfo_exists():
                    self._level_btn.configure(state="normal")
        finally:
            end_calibration_navigation_lock(self.base_window, self)

    def _present_level_calibration_result(self, success: bool, message: str, *, command_sent: bool) -> None:
        """Read back and stage trim results before releasing navigation."""
        # pylint: disable=duplicate-code
        if success:
            base_window = cast("Any", self.base_window)
            download_result = base_window.download_flight_controller_parameters(redownload=True)
            downloaded = not (isinstance(download_result, tuple) and not download_result[0])
            stale_files = refresh_parameter_editor_after_calibration(
                self.base_window,
                parameter_names_to_copy={"AHRS_TRIM_X", "AHRS_TRIM_Y"} if downloaded else set(),
                check_other_steps=True,
                redownload=False,
            )
            if not downloaded:
                message += "\n" + _("Could not download the new calibration values.")
            if stale_files:
                message += "\n" + _("Review stale AHRS trim values in: %(filenames)s") % {"filenames": ", ".join(stale_files)}
            showinfo(_("Calibration Result"), message)
        else:
            if command_sent:
                base_window = cast("Any", self.base_window)
                trim_names = {"AHRS_TRIM_X", "AHRS_TRIM_Y"}
                editor = base_window.parameter_editor
                old_values = {name: editor.fc_parameters.get(name) for name in trim_names}
                download_result = base_window.download_flight_controller_parameters(redownload=True, response_timeout=2.0)
                changed = sorted(name for name in trim_names if editor.fc_parameters.get(name) != old_values[name])
                stale_files = refresh_parameter_editor_after_calibration(
                    self.base_window, parameter_names_to_copy=changed, check_other_steps=True, redownload=False
                )
                if changed:
                    message += "\n" + _(
                        "The flight controller saved new trim values despite the failed acknowledgment: %(parameters)s."
                    ) % {"parameters": ", ".join(changed)}
                if stale_files:
                    message += "\n" + _("Review stale AHRS trim values in: %(filenames)s") % {
                        "filenames": ", ".join(stale_files)
                    }
                if not editor.fc_parameters or (isinstance(download_result, tuple) and not download_result[0]):
                    message += "\n" + _("Could not confirm whether the trim values were saved.")
            showerror(_("Calibration Failed"), message)
        # pylint: enable=duplicate-code

    def destroy(self) -> None:
        """Cancel pending polls before destroying the view."""
        stop_periodic_polling(self.after_cancel, self._poll_job)
        self._poll_job = None
        try:
            if self._calibration_in_progress:
                self._calibration_in_progress = False
                self.model.abort_level_calibration()
        finally:
            end_calibration_navigation_lock(self.base_window, self)
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
