"""
GUI for compass calibration plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator
SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import tkinter as tk
from argparse import ArgumentParser, Namespace
from collections.abc import Callable
from contextlib import suppress
from logging import error as logging_error
from logging import warning as logging_warning
from tkinter import messagebox, ttk
from tkinter.messagebox import showerror
from typing import Any, cast

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_compass_calibration import CompassCalibrationDataModel
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.plugin_constants import PLUGIN_COMPASS_CALIBRATION
from ardupilot_methodic_configurator.plugin_factory import plugin_factory


class CompassCalibrationInstructionsPopup(tk.Toplevel):
    """A small, tooltip-styled popup shown before calibration starts, explaining what to do."""

    _BG_COLOR = "#ffffe0"
    _BORDER_COLOR = "#d8d8a0"
    _KEY_COLOR = "#fffef0"

    def __init__(self, parent: tk.Widget, on_continue: Callable[[], None]) -> None:
        super().__init__(parent)
        self._parent = parent
        self._on_continue = on_continue
        self._width = 0
        self._height = 0

        self.overrideredirect(boolean=True)
        self.transient(cast("tk.Wm", parent))
        self.grab_set()

        self._setup_ui()
        self._resize_and_center()
        self.lift()
        self.focus_force()

    def _setup_ui(self) -> None:
        self.configure(bg=self._KEY_COLOR)
        with contextlib.suppress(tk.TclError):
            self.wm_attributes("-transparentcolor", self._KEY_COLOR)

        self.canvas = tk.Canvas(self, bg=self._KEY_COLOR, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        info_text = _(
            "Hold the vehicle in the air, keep it in\n"
            "front of you and horizontal.\n\n"
            "Then rotate it so that each side\n"
            "(front, back, left, right, top, and bottom)\n"
            "points down, until all progress bars\n"
            "reach 100%."
        )
        label = tk.Label(
            self.canvas,
            text=info_text,
            justify="center",
            bg=self._BG_COLOR,
            fg="black",
            font=("TkDefaultFont", 15),
        )
        button = ttk.Button(self.canvas, text=_("Continue"), command=self._on_continue_clicked)

        # Measure natural sizes so the rounded card can be sized to fit its content.
        label.update_idletasks()
        button.update_idletasks()
        label_w = label.winfo_reqwidth()
        label_h = label.winfo_reqheight()
        button_w = button.winfo_reqwidth()
        button_h = button.winfo_reqheight()

        pad_x, pad_top, gap, pad_bottom = 30, 25, 18, 25
        width = max(label_w, button_w) + pad_x * 2
        height = pad_top + label_h + gap + button_h + pad_bottom

        self.canvas.configure(width=width, height=height)

        self._draw_rounded_rect((0, 0, width, height), radius=22, fill=self._BG_COLOR, outline="")
        inset = 3
        self._draw_rounded_rect(
            (inset, inset, width - inset, height - inset),
            radius=22 - inset,
            fill="",
            outline=self._BORDER_COLOR,
            width=1,
        )

        self.canvas.create_window(width / 2, pad_top + label_h / 2, window=label, anchor="center")
        self.canvas.create_window(width / 2, pad_top + label_h + gap + button_h / 2, window=button, anchor="center")

        self._width = width
        self._height = height

    def _draw_rounded_rect(self, bbox: tuple[float, float, float, float], radius: int = 20, **kwargs) -> int:
        x1, y1, x2, y2 = bbox
        corners = [
            (x1 + radius, y1),
            (x2 - radius, y1),
            (x2, y1),
            (x2, y1 + radius),
            (x2, y2 - radius),
            (x2, y2),
            (x2 - radius, y2),
            (x1 + radius, y2),
            (x1, y2),
            (x1, y2 - radius),
            (x1, y1 + radius),
            (x1, y1),
        ]
        points = [coord for point in corners for coord in point]
        return self.canvas.create_polygon(points, smooth=True, **kwargs)

    def _on_continue_clicked(self) -> None:
        self.destroy()
        self._on_continue()

    def _resize_and_center(self) -> None:
        self.update_idletasks()
        width, height = self._width, self._height

        parent_x = self._parent.winfo_rootx()
        parent_y = self._parent.winfo_rooty()
        parent_width = self._parent.winfo_width()
        parent_height = self._parent.winfo_height()

        x = parent_x + (parent_width // 2) - (width // 2)
        y = parent_y + (parent_height // 2) - (height // 2)

        self.geometry(f"{width}x{height}+{x}+{y}")


class CompassCalibrationPopup(tk.Toplevel):  # pylint: disable=too-many-instance-attributes
    """A modern, borderless popup window with a custom draggable title bar."""

    def __init__(self, parent: tk.Widget, model: CompassCalibrationDataModel) -> None:
        super().__init__(parent)
        self.model = model
        self._parent = parent

        self.overrideredirect(boolean=True)
        self.transient(cast("tk.Wm", parent))
        self.grab_set()

        # Variables for custom window dragging
        self._drag_x = 0
        self._drag_y = 0

        self._timer_id: str | None = None
        self.progress_bars: dict[int, ttk.Progressbar] = {}
        self.completion_status: dict[int, bool] = {}

        self._setup_style()
        self._setup_ui()
        self._resize_and_center()
        self.lift()
        self.focus_force()
        self._timer_id = self.after(100, self._check_progress)

    def destroy(self) -> None:
        """Stop polling before destroying the popup."""
        self._stop_polling()
        super().destroy()

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        self._bg_color = style.lookup("TFrame", "background") or self.cget("bg")
        style.configure(
            "Horizontal.TProgressbar",
            borderwidth=0,
            thickness=24,
        )
        style.configure(
            "Done.Horizontal.TProgressbar",
            background="#8fbc8f",
            borderwidth=0,
            thickness=24,
            troughcolor=style.lookup("Horizontal.TProgressbar", "troughcolor"),
        )

    def _setup_ui(self) -> None:
        self.configure(bg=self._bg_color)
        outer_frame = tk.Frame(self, bg=self._bg_color, highlightthickness=0)
        outer_frame.pack(fill="both", expand=True)

        title_bar = tk.Frame(outer_frame, bg="#e0e0e0", relief="flat", bd=0)
        title_bar.pack(fill="x", side="top")

        title_bar.bind("<ButtonPress-1>", self._start_move)
        title_bar.bind("<B1-Motion>", self._do_move)

        title_label = tk.Label(
            title_bar, text=_("Calibrating Compasses"), bg="#e0e0e0", fg="black", font=("TkDefaultFont", 11, "bold")
        )
        title_label.pack(side="left", padx=10, pady=5)
        title_label.bind("<ButtonPress-1>", self._start_move)
        title_label.bind("<B1-Motion>", self._do_move)

        content_frame = ttk.Frame(outer_frame)
        content_frame.pack(fill="both", expand=True, padx=20, pady=20)

        self.hint_label = ttk.Label(
            content_frame,
            text=_("Keep moving the drone"),
            font=("TkDefaultFont", 11, "italic"),
        )
        self.hint_label.pack(pady=(0, 10))

        self.bars_frame = ttk.Frame(content_frame)
        self.bars_frame.pack(fill="both", expand=True, pady=5)
        self.rows_container = ttk.Frame(self.bars_frame)
        self.rows_container.pack(expand=True)

        self.cancel_button = ttk.Button(content_frame, text=_("Cancel Calibration"), command=self._on_cancel)
        self.cancel_button.pack(pady=(15, 0))

    def _start_move(self, event: tk.Event) -> None:
        self._drag_x = event.x
        self._drag_y = event.y

    def _do_move(self, event: tk.Event) -> None:
        x = self.winfo_x() + event.x - self._drag_x
        y = self.winfo_y() + event.y - self._drag_y
        self.geometry(f"+{x}+{y}")

    def _resize_and_center(self) -> None:
        self.update_idletasks()
        self.minsize(560, 320)

        width = max(self.winfo_reqwidth(), 560)
        height = max(self.winfo_reqheight(), 320)
        self.geometry(f"{width}x{height}")
        self.update_idletasks()

        parent_x = self._parent.winfo_rootx()
        parent_y = self._parent.winfo_rooty()
        parent_width = self._parent.winfo_width()
        parent_height = self._parent.winfo_height()

        x = parent_x + (parent_width // 2) - (width // 2)
        y = parent_y + (parent_height // 2) - (height // 2)

        self.geometry(f"{width}x{height}+{x}+{y}")

    def _stop_polling(self) -> None:
        """Cancel the periodic progress polling callback if it is active."""
        if self._timer_id:
            with suppress(tk.TclError):
                self.after_cancel(self._timer_id)
            self._timer_id = None

    def _check_progress(self) -> None:
        data_list = self.model.get_progress()

        if not data_list:
            self._timer_id = self.after(100, self._check_progress)
            return

        for raw_data in data_list:
            data: dict[str, Any] = cast("dict", raw_data)
            cid = data.get("compass_id", 0)

            if cid not in self.progress_bars:
                row = ttk.Frame(self.rows_container)
                row.pack(fill="x", pady=8)
                ttk.Label(
                    row, text=_("Compass {compass_id}").format(compass_id=cid), width=10, font=("TkDefaultFont", 11, "bold")
                ).pack(side="left")
                progress_bar = ttk.Progressbar(row, orient="horizontal", length=320, mode="determinate", maximum=100)
                progress_bar.pack(side="left", expand=True, fill="x", padx=10)

                self.progress_bars[cid] = progress_bar
                self.completion_status[cid] = False
                self.update_idletasks()
                self._resize_and_center()

            if data["type"] == "PROGRESS":
                pct = data.get("completion_pct", 0)
                self.progress_bars[cid]["value"] = int(pct)

            elif data["type"] == "REPORT":
                # Only mark as done if the calibration was successful (status 4 = MAG_CAL_SUCCESS)
                if data.get("status") == 4 or data.get("saved"):
                    progress_bar = self.progress_bars[cid]
                    progress_bar.stop()
                    progress_bar["maximum"] = 100
                    progress_bar["value"] = 100
                    progress_bar.configure(style="Done.Horizontal.TProgressbar")
                    progress_bar.update_idletasks()
                    self.completion_status[cid] = True
                else:
                    # The calibration failed; try to cancel the session before closing the popup.
                    self._stop_polling()
                    success, error_msg = self.model.cancel_calibration()
                    if success:
                        self.model.finish_calibration()
                        messagebox.showerror(
                            _("Calibration Failed"),
                            _("Calibration for Compass {compass_id} failed. Please try again.").format(compass_id=cid),
                            parent=self,
                        )
                        self.destroy()
                    else:
                        messagebox.showerror(_("Failed to Cancel"), error_msg, parent=self)
                        self._timer_id = self.after(100, self._check_progress)
                    return

        if self.completion_status and all(self.completion_status.values()):
            if self._timer_id:
                self.after_cancel(self._timer_id)
            self.model.finish_calibration()
            messagebox.showinfo(_("Calibration Complete"), _("All compasses successfully calibrated and saved!"), parent=self)
            self.destroy()
        else:
            self._timer_id = self.after(100, self._check_progress)

    def _on_cancel(self) -> None:
        self._stop_polling()
        success, error_msg = self.model.cancel_calibration()
        if success:
            self.model.finish_calibration()
            messagebox.showinfo(_("Cancelled"), _("Compass calibration was cancelled."), parent=self)
            self.destroy()
            return

        messagebox.showerror(_("Failed to Cancel"), error_msg, parent=self)
        self._timer_id = self.after(100, self._check_progress)


# pylint: disable=too-many-ancestors
class CompassCalibrationView(ttk.Frame):
    """Main GUI view for the compass calibration plugin inside AMC."""

    def __init__(
        self,
        parent: tk.Frame | ttk.Frame,
        model: CompassCalibrationDataModel,
        base_window: BaseWindow,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        self._instructions_popup: CompassCalibrationInstructionsPopup | None = None
        self._calibration_popup: CompassCalibrationPopup | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="x", expand=False, padx=10, pady=10)

        self.start_button = ttk.Button(main_frame, text=_("Start Compass Calibration"), command=self._on_start)
        self.start_button.pack(pady=5)

    def _on_start(self) -> None:
        self._instructions_popup = CompassCalibrationInstructionsPopup(self.winfo_toplevel(), self._begin_calibration)

    def _begin_calibration(self) -> None:
        success, error_msg = self.model.start_calibration()
        if success:
            self._calibration_popup = CompassCalibrationPopup(self.winfo_toplevel(), self.model)
        else:
            messagebox.showerror(_("Failed to Start"), error_msg, parent=self)


def _create_compass_calibration_view(
    parent: tk.Frame | ttk.Frame,
    model: object,
    base_window: object,
) -> CompassCalibrationView:
    return CompassCalibrationView(parent, model, base_window)  # type: ignore[arg-type]


def register_compass_calibration_plugin() -> None:
    plugin_factory.register(PLUGIN_COMPASS_CALIBRATION, _create_compass_calibration_view)


class CompassCalibrationWindow(BaseWindow):  # pragma: no cover
    """
    Standalone window for the compass calibration GUI.

    Used for development and testing only.
    """

    def __init__(self, model: CompassCalibrationDataModel) -> None:
        super().__init__()
        self.model = model  # Store model reference for tests
        self.root.title(_("ArduPilot Compass Calibration"))
        self.root.geometry(self.calculate_scaled_geometry(600, 400))
        self.view = CompassCalibrationView(self.main_frame, model, self)
        self.view.pack(fill="both", expand=True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self) -> None:
        """Handle window close event."""
        with suppress(tk.TclError, AttributeError):
            if self.model._is_calibrating:  # noqa: SLF001 #pylint: disable=protected-access
                self.model.cancel_calibration()
        self.root.destroy()


def argument_parser() -> Namespace:  # pragma: no cover
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.
    This is just for testing the script. Production code will not call this function.

    Returns:
        argparse.Namespace: An object containing the parsed arguments.

    """
    # The rest of the file should not have access to any of these backends.
    # It must use the data_model layer instead of accessing the backends directly.
    # pylint: disable=import-outside-toplevel
    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController  # noqa: PLC0415
    # pylint: enable=import-outside-toplevel

    parser = ArgumentParser(
        description=_(
            "This main is for testing and development only. Usually, the CompassCalibrationView is called from another script"
        )
    )
    parser = FlightController.add_argparse_arguments(parser)
    return add_common_arguments(parser).parse_args()


# pylint: disable=duplicate-code
def main() -> None:  # pragma: no cover
    from ardupilot_methodic_configurator.__main__ import (  # pylint: disable=import-outside-toplevel # noqa: PLC0415
        ApplicationState,
        initialize_flight_controller,
        setup_logging,
    )

    args = argument_parser()
    state = ApplicationState(args)
    setup_logging(state)
    logging_warning(
        _("This main is for testing and development only. Usually, the CompassCalibrationView is called from another script")
    )
    initialize_flight_controller(state)

    try:
        data_model = CompassCalibrationDataModel(state.flight_controller)
        window = CompassCalibrationWindow(data_model)
        window.root.mainloop()
    except Exception as e:  # pylint: disable=broad-exception-caught
        logging_error("Failed to start CompassCalibrationWindow: %(error)s", {"error": e})
        # Show error to user
        showerror(_("Error"), f"Failed to start compass calibration: {e}")
    finally:
        if state.flight_controller:
            state.flight_controller.disconnect()  # Disconnect from the flight controller


if __name__ == "__main__":  # pragma: no cover
    main()
