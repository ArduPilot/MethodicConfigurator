"""
GUI for AHRS orientation helper plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import tkinter as tk
from tkinter import Frame, ttk
from tkinter.messagebox import askyesno, showerror, showinfo
from typing import TYPE_CHECKING

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_parameter_editor import (
    InvalidParameterNameError,
    OperationNotPossibleError,
    ParameterValueUpdateStatus,
)
from ardupilot_methodic_configurator.plugins.imu_helpers import (
    ImuPollHandlers,
    poll_imu_periodically,
    stop_periodic_polling,
)
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_AHRS_ORIENTATION
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
    from ardupilot_methodic_configurator.plugins.data_model_ahrs_orientation import (
        AhrsOrientationDataModel,
        AhrsOrientationEstimate,
    )

_IMU_POLL_INTERVAL_MS = 200


class AhrsOrientationView(Frame):  # pylint: disable=too-many-instance-attributes
    """GUI for helping users estimate AHRS_ORIENTATION."""

    def __init__(
        self,
        parent: tk.Frame | ttk.Frame,
        model: AhrsOrientationDataModel,
        base_window: BaseWindow,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self.base_window = base_window

        self._imu_poll_job: str | None = None
        self._latest_imu: tuple[float, float, float] | None = None
        self._imu_poll_handlers = ImuPollHandlers.for_view(self, _IMU_POLL_INTERVAL_MS)

        self._wizard_active: bool = False
        self._step_index: int = 0
        self._steps: tuple[str, str, str] = self.model.get_required_steps()

        self._setup_ui()
        self._start_imu_polling()

    def _setup_ui(self) -> None:
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True)

        manual_option_frame = ttk.LabelFrame(
            main_frame,
            text=_("Option 1 - Set AHRS_ORIENTATION manually"),
            padding=10,
        )
        manual_option_frame.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Label(
            manual_option_frame,
            text=_(
                "Use this option if you know the vehicle orientation.\n"
                "Set AHRS_ORIENTATION manually in the parameter list on the right."
            ),
            justify="left",
            wraplength=640,
        ).pack(anchor="w")

        automated_option_frame = ttk.LabelFrame(
            main_frame,
            text=_("Option 2 - Determine AHRS_ORIENTATION automatically"),
            padding=10,
        )
        automated_option_frame.pack(fill="x", padx=10)
        info_text = _(
            "Use this option if you do not know the vehicle orientation.\n"
            "This assistant estimates AHRS_ORIENTATION from three vehicle positions:\n"
            "LEVEL, NOSE DOWN, and RIGHT SIDE DOWN.\n\n"
            "It compensates for the current preset AHRS_ORIENTATION. If a custom\n"
            "orientation is active, set AHRS_ORIENTATION to 0 and upload parameters first."
        )
        ttk.Label(automated_option_frame, text=info_text, justify="left", wraplength=640).pack(anchor="w", pady=(0, 16))

        self._wizard_frame = ttk.Frame(automated_option_frame)
        self._wizard_frame.pack(fill="x")

        self._wizard_instruction_var = tk.StringVar(value="")
        self._wizard_progress_var = tk.StringVar(value="")
        self._recommendation_var = tk.StringVar(value="")

        ttk.Label(self._wizard_frame, textvariable=self._wizard_instruction_var, wraplength=620, justify="left").pack(
            anchor="w", pady=(0, 6)
        )
        ttk.Label(self._wizard_frame, textvariable=self._wizard_progress_var).pack(anchor="w", pady=(0, 10))

        wizard_actions = ttk.Frame(self._wizard_frame)
        wizard_actions.pack(anchor="w")

        self._continue_btn = ttk.Button(wizard_actions, text=_("Continue"), command=self._on_continue, state="disabled")
        self._continue_btn.pack(side="left", padx=(0, 8))

        self._cancel_btn = ttk.Button(wizard_actions, text=_("Cancel"), command=self._on_cancel)
        self._cancel_btn.pack(side="left")

        ttk.Label(self._wizard_frame, textvariable=self._recommendation_var, justify="left", wraplength=620).pack(
            anchor="w", pady=(10, 0)
        )

    def _on_start_detection(self) -> None:
        if not self.model.is_connected():
            showerror(_("Not Connected"), _("Flight controller not connected"))
            return

        prerequisites_ok, prerequisites_message = self.model.validate_detection_prerequisites()
        if not prerequisites_ok:
            showerror(_("Auto-detection Not Ready"), prerequisites_message)
            return

        self.model.reset_sequence()
        self._step_index = 0
        self._wizard_active = True
        self._recommendation_var.set("")
        self._continue_btn.configure(state="normal")
        self._update_wizard_text()

    def _on_continue(self) -> None:
        if not self._wizard_active:
            self._on_start_detection()
            return

        step_name = self._steps[self._step_index]
        ok, msg = self.model.record_sample(step_name, self._latest_imu)
        if not ok:
            showerror(_("Capture Failed"), msg)
            return

        self._step_index += 1
        if self._step_index < len(self._steps):
            self._update_wizard_text()
            return

        self._wizard_active = False
        self._continue_btn.configure(state="normal")
        self._wizard_instruction_var.set(_("Auto-detection complete."))
        self._wizard_progress_var.set(_("Review the recommendation below or press Continue to start again."))

        ok_est, estimate, est_msg = self.model.estimate_orientation()
        if not ok_est or estimate is None:
            self._recommendation_var.set(est_msg)
            showerror(_("Estimation Failed"), est_msg)
            return

        if estimate.is_preset_match:
            if not self._apply_parameter_value("AHRS_ORIENTATION", f"{estimate.best_code}"):
                self._recommendation_var.set(_("Could not write AHRS_ORIENTATION into the parameter table."))
                showerror(
                    _("Parameter Update Failed"),
                    _("Could not write AHRS_ORIENTATION into the parameter table."),
                )
                return
            self._refresh_parameter_table()
            result_text = _(
                "AHRS_ORIENTATION was set to %(code)d (%(name)s). Match score: %(match_score).1f%%. "
                "Press upload to apply the changes."
            ) % {
                "code": estimate.best_code,
                "name": estimate.best_name,
                "match_score": estimate.match_score_percent,
            }
            self._recommendation_var.set(result_text)
            showinfo(_("AHRS Orientation Estimate"), result_text)
        else:
            prompt_text = _(
                "Could not identify a sufficiently distinct preset orientation "
                "(best: %(code)d %(name)s, match score %(match_score).1f%%).\n\n"
                "Yes: use CUST_ROT1_ROLL/PITCH/YAW and set AHRS_ORIENTATION to 101 (Custom 1).\n"
                "No: re-do the estimation process."
            ) % {
                "code": estimate.best_code,
                "name": estimate.best_name,
                "match_score": estimate.match_score_percent,
            }
            self._recommendation_var.set(prompt_text)

            use_custom = askyesno(_("Low Confidence Estimate"), prompt_text)
            if use_custom:
                if self._apply_custom_orientation(estimate):
                    result_text = _(
                        "Set CUST_ROT_ENABLE=1, "
                        "Applied CUST_ROT1_ROLL=%(roll).1f, CUST_ROT1_PITCH=%(pitch).1f, "
                        "CUST_ROT1_YAW=%(yaw).1f and set AHRS_ORIENTATION=101 (Custom 1). "
                        "Upload the changes to use Custom 1 rotation."
                    ) % {
                        "roll": estimate.custom_roll_deg,
                        "pitch": estimate.custom_pitch_deg,
                        "yaw": estimate.custom_yaw_deg,
                    }
                    self._recommendation_var.set(result_text)
                    showinfo(_("Custom Orientation Applied"), result_text)
                else:
                    self._recommendation_var.set(_("Could not apply Custom 1 orientation parameters in the parameter table."))
                    showerror(
                        _("Parameter Update Failed"),
                        _("Could not apply Custom 1 orientation parameters in the parameter table."),
                    )
                return

            self._on_start_detection()

    def _on_cancel(self) -> None:
        self._wizard_active = False
        self._step_index = 0
        self.model.reset_sequence()
        self._wizard_instruction_var.set(_("Press Continue to start the auto-detection wizard."))
        self._wizard_progress_var.set("")

    def _apply_custom_orientation(self, estimate: AhrsOrientationEstimate) -> bool:
        required_parameters = [
            "CUST_ROT_ENABLE",
            "AHRS_ORIENTATION",
            "CUST_ROT1_ROLL",
            "CUST_ROT1_PITCH",
            "CUST_ROT1_YAW",
        ]
        for param_name in required_parameters:
            if not self._ensure_parameter_exists(param_name):
                return False

        updates = [
            ("CUST_ROT_ENABLE", "1"),
            ("CUST_ROT1_ROLL", f"{estimate.custom_roll_deg:.1f}"),
            ("CUST_ROT1_PITCH", f"{estimate.custom_pitch_deg:.1f}"),
            ("CUST_ROT1_YAW", f"{estimate.custom_yaw_deg:.1f}"),
            ("AHRS_ORIENTATION", "101"),
        ]
        for param_name, value in updates:
            if not self._apply_parameter_value(param_name, value):
                return False

        self._refresh_parameter_table()
        return True

    def _ensure_parameter_exists(self, param_name: str) -> bool:
        parameter_editor = getattr(self.base_window, "parameter_editor", None)
        if parameter_editor is None:
            return False
        if param_name in parameter_editor.current_step_parameters:
            return True
        try:
            return bool(parameter_editor.add_parameter_to_current_file(param_name))
        except (AttributeError, InvalidParameterNameError, OperationNotPossibleError, TypeError, ValueError):
            return False

    def _apply_parameter_value(self, param_name: str, value: str) -> bool:
        parameter_editor = getattr(self.base_window, "parameter_editor", None)
        if parameter_editor is None:
            return False

        result = parameter_editor.update_parameter_value(param_name, value, include_range_check=False)
        return bool(result.status in (ParameterValueUpdateStatus.UPDATED, ParameterValueUpdateStatus.UNCHANGED))

    def _refresh_parameter_table(self) -> None:
        parameter_editor_table = getattr(self.base_window, "parameter_editor_table", None)
        if parameter_editor_table is None:
            return
        show_only_differences_var = getattr(self.base_window, "show_only_differences", None)
        show_only_differences = show_only_differences_var.get() if show_only_differences_var else False
        gui_complexity = getattr(self.base_window, "gui_complexity", "simple")
        parameter_editor_table.repopulate_table(show_only_differences=show_only_differences, gui_complexity=gui_complexity)

    def _update_wizard_text(self) -> None:
        step_name = self._steps[self._step_index]
        if step_name == "LEVEL":
            instruction = _(
                "Place the vehicle LEVEL, keep it perfectly still, then click Continue to begin automatic detection."
            )
        elif step_name == "NOSE DOWN":
            instruction = _("Place the vehicle NOSE DOWN, keep it perfectly still, then click Continue.")
        else:
            instruction = _("Place the vehicle on its RIGHT side, keep it perfectly still, then click Continue.")

        self._wizard_instruction_var.set(instruction)
        self._wizard_progress_var.set(
            _("Step %(current)d/%(total)d: %(name)s")
            % {"current": self._step_index + 1, "total": len(self._steps), "name": _(step_name)}
        )

    def _start_imu_polling(self) -> None:
        self._imu_poll_job = poll_imu_periodically(self.after, self._imu_poll_job, self._imu_poll_handlers)

    def _stop_imu_polling(self) -> None:
        stop_periodic_polling(self.after_cancel, self._imu_poll_job)
        self._imu_poll_job = None

    def _handle_live_imu_sample(self, imu: tuple[float, float, float]) -> None:
        self._latest_imu = imu
        self._continue_btn.configure(state="normal")

    def _handle_no_live_imu_sample(self) -> None:
        if self._wizard_active:
            self._continue_btn.configure(state="disabled")

    def _store_imu_poll_job(self, job_id: str) -> None:
        """Keep the currently scheduled timer id available for cancellation."""
        self._imu_poll_job = job_id

    def on_activate(self) -> None:
        """Called when plugin view becomes visible."""
        self._start_imu_polling()
        if not self._wizard_active:
            self._on_start_detection()

    def on_deactivate(self) -> None:
        """Called when plugin view is hidden."""
        self._stop_imu_polling()
        self.model.stop_imu_monitoring()
        self._wizard_active = False
        self._continue_btn.configure(state="disabled")

    def destroy(self) -> None:
        """Cleanup resources when plugin is removed."""
        self._stop_imu_polling()
        super().destroy()


def _create_ahrs_orientation_view(
    parent: tk.Frame | ttk.Frame,
    model: object,
    base_window: object,
) -> AhrsOrientationView:
    """Factory function to create AhrsOrientationView instances."""
    return AhrsOrientationView(parent, model, base_window)  # type: ignore[arg-type]


def _create_ahrs_orientation_model(context: PluginModelContext) -> AhrsOrientationDataModel:
    """Create the plugin data model from registered application dependencies."""
    from ardupilot_methodic_configurator.plugins.data_model_ahrs_orientation import (  # noqa: PLC0415 # pylint: disable=import-outside-toplevel
        AhrsOrientationDataModel,
    )

    return AhrsOrientationDataModel(context.flight_controller)


def register_ahrs_orientation_plugin() -> None:
    """Register the AHRS orientation plugin with the factory."""
    plugin_factory.register(PLUGIN_AHRS_ORIENTATION, _create_ahrs_orientation_view, _create_ahrs_orientation_model)
