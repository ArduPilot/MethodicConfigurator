"""
GUI for RC calibration plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import ArgumentParser, Namespace
from contextlib import suppress
from logging import debug as logging_debug
from logging import error as logging_error
from logging import warning as logging_warning
from tkinter import ttk
from tkinter.messagebox import showerror

from PIL import ImageTk

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_rc_calibration import RCCalibrationDataModel
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_calibration_popup_base import CalibrationPopupBase
from ardupilot_methodic_configurator.plugin_constants import PLUGIN_RC_CALIBRATION
from ardupilot_methodic_configurator.plugin_factory import plugin_factory
from ardupilot_methodic_configurator.renderer_3d_quadcopter import QuadcopterRenderer


class RCCalibrationPopup(CalibrationPopupBase["RCCalibrationDataModel"]):  # pylint: disable=too-many-instance-attributes
    """A modern, borderless popup window with a custom draggable title bar for RC monitoring."""

    _MIN_WIDTH = 600
    _MIN_HEIGHT = 500

    def __init__(self, parent: tk.Widget, model: RCCalibrationDataModel) -> None:
        super().__init__(parent, model)
        self.stick_data: dict[str, float] = {
            "ROLL": 0.0,
            "PITCH": 0.0,
            "THROTTLE": 0.0,
            "YAW": 0.0,
        }
        self.flight_mode: str = "No Data"
        self.channels: list[dict] = []

        self.renderer = QuadcopterRenderer()
        self._setup_style()
        self._setup_ui()
        self._resize_and_center()
        self.root.lift()
        self.root.focus_force()
        self._timer_id = self.root.after(100, self._check_telemetry)
        logging_debug(_("RC calibration progress popup created and polling scheduled."))

    def _setup_ui(self) -> None:
        content_frame = self._create_framed_ui(_("Live Monitor"))

        # Preview Stages Section
        preview_frame = ttk.LabelFrame(content_frame, text=_("Preview Stages"), padding=10)
        preview_frame.pack(fill="x", pady=(0, 15))

        # 3D Model Preview using OpenGL
        self.preview_label = ttk.Label(preview_frame, text=_("Waiting for live RC input..."), font=("TkDefaultFont", 10))
        self.preview_label.pack(pady=5)

        # Stick Preview Section
        stick_preview_frame = ttk.LabelFrame(content_frame, text=_("Stick Preview"), padding=10)
        stick_preview_frame.pack(fill="x", pady=5)

        self.stick_bars: dict[str, ttk.Progressbar] = {}
        for stick in ["ROLL", "PITCH", "THROTTLE", "YAW"]:
            row = ttk.Frame(stick_preview_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=stick, width=10, font=("TkDefaultFont", 10, "bold")).pack(side="left")
            pb = ttk.Progressbar(row, orient="horizontal", length=300, mode="determinate", maximum=100)
            pb.pack(side="left", expand=True, fill="x", padx=10)
            self.stick_bars[stick] = pb

        # Flight Mode Section
        mode_frame = ttk.Frame(content_frame)
        mode_frame.pack(fill="x", pady=10)
        ttk.Label(mode_frame, text=_("Flight Mode:"), font=("TkDefaultFont", 11, "bold")).pack(side="left")
        self.mode_label = ttk.Label(mode_frame, text="No Data", font=("TkDefaultFont", 11))
        self.mode_label.pack(side="left", padx=10)

        # Channel List Section
        channel_frame = ttk.LabelFrame(content_frame, text=_("Channels"), padding=10)
        channel_frame.pack(fill="both", expand=True, pady=5)

        self.channel_list_frame = ttk.Frame(channel_frame)
        self.channel_list_frame.pack(fill="both", expand=True)

    def _check_telemetry(self) -> None:  # pylint: disable=too-many-locals
        telemetry = self.model.get_rc_telemetry()

        if not telemetry:
            self._polls_without_updates += 1
            if self._polls_without_updates == 50 and not self._no_telemetry_warning_emitted:
                self._no_telemetry_warning_emitted = True
                logging_warning(
                    _("No RC telemetry has arrived after %(polls)d polls."), {"polls": self._polls_without_updates}
                )
            self._timer_id = self.root.after(100, self._check_telemetry)
            return

        self._polls_without_updates = 0
        self._no_telemetry_warning_emitted = False

        # Update Flight Mode
        self.flight_mode = telemetry.get("flight_mode", "No Data")
        self.mode_label.configure(text=self.flight_mode)

        # Update Stick Preview
        # Assuming telemetry has "roll", "pitch", "throttle", "yaw" in range -1000 to 1000
        for stick in ["ROLL", "PITCH", "THROTTLE", "YAW"]:
            val = telemetry.get(stick.lower(), 0.0)
            # Map -1000...1000 to 0...100
            pct = ((val + 1000) / 2000) * 100
            self.stick_bars[stick]["value"] = int(max(0, min(100, pct)))

        # Update Channel List
        channels = telemetry.get("channels", [])
        # Clear existing list
        for widget in self.channel_list_frame.winfo_children():
            widget.destroy()

        # Rebuild list
        for ch in channels:
            row = ttk.Frame(self.channel_list_frame)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=ch.get("name", "?"), width=6, font=("TkDefaultFont", 9, "bold")).pack(side="left")
            ttk.Label(row, text=f"{ch.get('value', 0)} µs", width=10).pack(side="left")

        # Update 3D Preview
        roll = telemetry.get("roll", 0.0)
        pitch = telemetry.get("pitch", 0.0)
        yaw = telemetry.get("yaw", 0.0)
        throttle = telemetry.get("throttle", 0.0)

        # Convert -1000...1000 to -1.0...1.0
        roll_norm = roll / 1000.0
        pitch_norm = pitch / 1000.0
        yaw_norm = yaw / 1000.0
        throttle_norm = throttle / 1000.0

        pil_img = self.renderer.render(roll_norm, pitch_norm, yaw_norm, throttle_norm)
        tk_img = ImageTk.PhotoImage(pil_img)
        self.preview_label.configure(image=tk_img)
        self.preview_label.image = tk_img  # type: ignore[attr-defined] # Keep reference

        self._timer_id = self.root.after(100, self._check_telemetry)


class RCCalibrationView(ttk.Frame):  # pylint: disable=too-many-ancestors, too-many-instance-attributes
    """Main GUI view for the RC calibration plugin inside AMC."""

    def __init__(
        self,
        parent: tk.Frame | ttk.Frame,
        model: RCCalibrationDataModel,
        base_window: BaseWindow,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        self._timer_id: str | None = None
        self._polls_without_updates = 0
        self._no_telemetry_warning_emitted = False
        self.flight_mode: str = "No Data"
        self.renderer = QuadcopterRenderer()
        self._setup_style()
        self._setup_ui()
        self._timer_id = self.after(100, self._check_telemetry)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        self._bg_color = style.lookup("TFrame", "background") or self.cget("bg")
        # Configure the frame style to use our background color
        style.configure("RCCalibration.TFrame", background=self._bg_color)

    def _setup_ui(self) -> None:
        # Apply the custom style class to this ttk.Frame
        self.configure(style="RCCalibration.TFrame")
        outer_frame = tk.Frame(self, bg=self._bg_color, highlightthickness=0)
        outer_frame.pack(fill="both", expand=True)

        # Calibration control buttons
        control_frame = ttk.Frame(outer_frame)
        control_frame.pack(fill="x", padx=10, pady=(10, 0))

        self._start_btn = ttk.Button(
            control_frame,
            text=_("Start Calibration"),
            command=self._on_start_calibration,
        )
        self._start_btn.pack(side="left", padx=5)

        self._finish_btn = ttk.Button(
            control_frame,
            text=_("Finish Calibration"),
            state="disabled",
            command=self._on_finish_calibration,
        )
        self._finish_btn.pack(side="left", padx=5)

        self._cancel_btn = ttk.Button(
            control_frame,
            text=_("Cancel"),
            state="disabled",
            command=self._on_cancel_calibration,
        )
        self._cancel_btn.pack(side="left", padx=5)

        self._status_label = ttk.Label(control_frame, text=_("Move sticks to monitor RC input."), foreground="gray")
        self._status_label.pack(side="left", padx=10)

        content_frame = ttk.Frame(outer_frame)
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Preview Stages Section
        preview_frame = ttk.LabelFrame(content_frame, text=_("Preview Stages"), padding=10)
        preview_frame.pack(fill="x", pady=(0, 15))

        # 3D Model Preview using OpenGL
        self.preview_label = ttk.Label(preview_frame, text=_("Waiting for live RC input..."), font=("TkDefaultFont", 10))
        self.preview_label.pack(pady=5)

        # Stick Preview Section
        stick_preview_frame = ttk.LabelFrame(content_frame, text=_("Stick Preview"), padding=10)
        stick_preview_frame.pack(fill="x", pady=5)

        self.stick_bars: dict[str, ttk.Progressbar] = {}
        for stick in ["ROLL", "PITCH", "THROTTLE", "YAW"]:
            row = ttk.Frame(stick_preview_frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=stick, width=10, font=("TkDefaultFont", 10, "bold")).pack(side="left")
            pb = ttk.Progressbar(row, orient="horizontal", length=300, mode="determinate", maximum=100)
            pb.pack(side="left", expand=True, fill="x", padx=10)
            self.stick_bars[stick] = pb

        # Flight Mode Section
        mode_frame = ttk.Frame(content_frame)
        mode_frame.pack(fill="x", pady=10)
        ttk.Label(mode_frame, text=_("Flight Mode:"), font=("TkDefaultFont", 11, "bold")).pack(side="left")
        self.mode_label = ttk.Label(mode_frame, text="No Data", font=("TkDefaultFont", 11))
        self.mode_label.pack(side="left", padx=10)

        # Channel List Section
        channel_frame = ttk.LabelFrame(content_frame, text=_("Channels"), padding=10)
        channel_frame.pack(fill="both", expand=True, pady=5)

        self.channel_list_frame = ttk.Frame(channel_frame)
        self.channel_list_frame.pack(fill="both", expand=True)

    def _on_start_calibration(self) -> None:
        success, error_msg = self.model.start_calibration()
        if success:
            self._start_btn.configure(state="disabled")
            self._finish_btn.configure(state="normal")
            self._cancel_btn.configure(state="normal")
            self._status_label.configure(
                text=_("Calibrating — move all sticks and switches to their extremes, then click Finish."),
                foreground="blue",
            )
        else:
            self._status_label.configure(text=error_msg, foreground="red")

    def _on_finish_calibration(self) -> None:
        self.model.finish_calibration()
        self._start_btn.configure(state="normal")
        self._finish_btn.configure(state="disabled")
        self._cancel_btn.configure(state="disabled")
        self._status_label.configure(
            text=_("Calibration saved. You may re-calibrate or close this panel."),
            foreground="green",
        )

    def _on_cancel_calibration(self) -> None:
        self.model.cancel_calibration()
        self._start_btn.configure(state="normal")
        self._finish_btn.configure(state="disabled")
        self._cancel_btn.configure(state="disabled")
        self._status_label.configure(text=_("Calibration cancelled."), foreground="gray")

    def _stop_polling(self) -> None:
        if self._timer_id:
            with suppress(tk.TclError):
                self.after_cancel(self._timer_id)
            self._timer_id = None

    def _check_telemetry(self) -> None:  # pylint: disable=too-many-locals
        telemetry = self.model.get_rc_telemetry()

        if not telemetry:
            self._polls_without_updates += 1
            if self._polls_without_updates == 50 and not self._no_telemetry_warning_emitted:
                self._no_telemetry_warning_emitted = True
                logging_warning(
                    _("No RC telemetry has arrived after %(polls)d polls."), {"polls": self._polls_without_updates}
                )
            self._timer_id = self.after(100, self._check_telemetry)
            return

        self._polls_without_updates = 0
        self._no_telemetry_warning_emitted = False

        # Update Flight Mode
        self.flight_mode = telemetry.get("flight_mode", "No Data")
        self.mode_label.configure(text=self.flight_mode)

        # Update Stick Preview
        # Assuming telemetry has "roll", "pitch", "throttle", "yaw" in range -1000 to 1000
        for stick in ["ROLL", "PITCH", "THROTTLE", "YAW"]:
            val = telemetry.get(stick.lower(), 0.0)
            # Map -1000...1000 to 0...100
            pct = ((val + 1000) / 2000) * 100
            self.stick_bars[stick]["value"] = int(max(0, min(100, pct)))

        # Update Channel List
        channels = telemetry.get("channels", [])
        # Clear existing list
        for widget in self.channel_list_frame.winfo_children():
            widget.destroy()

        # Rebuild list
        for ch in channels:
            row = ttk.Frame(self.channel_list_frame)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=ch.get("name", "?"), width=6, font=("TkDefaultFont", 9, "bold")).pack(side="left")
            ttk.Label(row, text=f"{ch.get('value', 0)} µs", width=10).pack(side="left")

        # Update 3D Preview
        roll = telemetry.get("roll", 0.0)
        pitch = telemetry.get("pitch", 0.0)
        yaw = telemetry.get("yaw", 0.0)
        throttle = telemetry.get("throttle", 0.0)

        # Convert -1000...1000 to -1.0...1.0
        roll_norm = roll / 1000.0
        pitch_norm = pitch / 1000.0
        yaw_norm = yaw / 1000.0
        throttle_norm = throttle / 1000.0

        pil_img = self.renderer.render(roll_norm, pitch_norm, yaw_norm, throttle_norm)
        tk_img = ImageTk.PhotoImage(pil_img)
        self.preview_label.configure(image=tk_img)
        self.preview_label.image = tk_img  # type: ignore[attr-defined] # Keep reference

        self._timer_id = self.after(100, self._check_telemetry)

    def destroy(self) -> None:
        """Stop the polling loop before destroying the widget."""
        self._stop_polling()
        super().destroy()


def _create_rc_calibration_view(
    parent: tk.Frame | ttk.Frame,
    model: object,
    base_window: object,
) -> "RCCalibrationView":
    """
    Factory function to create RCCalibrationView instances.

    This function trusts that the caller provides the correct types
    as per the plugin protocol (duck typing approach).

    Args:
        parent: The parent frame
        model: The RCCalibrationDataModel instance (passed as object for protocol compliance)
        base_window: The BaseWindow instance (passed as object for protocol compliance)

    Returns:
        A new RCCalibrationView instance

    """
    return RCCalibrationView(parent, model, base_window)  # type: ignore[arg-type]


def register_rc_calibration_plugin() -> None:
    """Register the RC calibration plugin with the factory."""
    plugin_factory.register(PLUGIN_RC_CALIBRATION, _create_rc_calibration_view)


class RCCalibrationWindow(BaseWindow):  # pragma: no cover
    """
    Standalone window for the RC calibration GUI.

    Used for development and testing only.
    """

    def __init__(self, model: RCCalibrationDataModel) -> None:
        super().__init__()
        self.model = model  # Store model reference for tests
        self.root.title(_("ArduPilot RC Calibration"))
        self.root.geometry(self.calculate_scaled_geometry(600, 400))
        self.view = RCCalibrationView(self.main_frame, model, self)
        self.view.pack(fill="both", expand=True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # pylint: disable=duplicate-code
    def on_close(self) -> None:
        """Handle window close event."""
        with suppress(tk.TclError, AttributeError):
            if self.model._is_calibrating:  # noqa: SLF001 #pylint: disable=protected-access
                self.model.cancel_calibration()
        self.root.destroy()

    # pylint: enable=duplicate-code


# pylint: disable=duplicate-code
def argument_parser() -> Namespace:  # pragma: no cover
    from ardupilot_methodic_configurator.backend_flightcontroller import (  # pylint: disable=import-outside-toplevel # noqa: PLC0415
        FlightController,
    )

    parser = ArgumentParser(
        description=_(
            "This main is for testing and development only. Usually, the RCCalibrationView is called from another script"
        )
    )
    parser = FlightController.add_argparse_arguments(parser)
    return add_common_arguments(parser).parse_args()


# pylint: enable=duplicate-code


def main() -> None:  # pragma: no cover
    # pylint: disable=duplicate-code
    from ardupilot_methodic_configurator.__main__ import (  # pylint: disable=import-outside-toplevel # noqa: PLC0415
        ApplicationState,
        initialize_flight_controller,
        setup_logging,
    )

    args = argument_parser()
    state = ApplicationState(args)
    setup_logging(state)
    logging_warning(
        _("This main is for testing and development only. Usually, the RCCalibrationView is called from another script")
    )
    initialize_flight_controller(state)
    # pylint: enable=duplicate-code

    try:
        data_model = RCCalibrationDataModel(state.flight_controller)
        window = RCCalibrationWindow(data_model)
        window.root.mainloop()
    except Exception as e:  # pylint: disable=broad-exception-caught
        logging_error("Failed to start RCCalibrationWindow: %(error)s", {"error": e})
        # Show error to user
        showerror(_("Error"), _("Failed to start RC calibration: %(error)s") % {"error": e})
    finally:
        if state.flight_controller:
            state.flight_controller.disconnect()  # Disconnect from the flight controller


if __name__ == "__main__":  # pragma: no cover
    main()
