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
from logging import debug as logging_debug
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
        self._polls_without_updates = 0
        self._no_telemetry_warning_emitted = False
        self._expected_compass_ids = self._load_expected_compass_ids()
        self.progress_bars: dict[int, ttk.Progressbar] = {}
        self.completion_status: dict[int, bool] = {}

        self._setup_style()
        self._setup_ui()
        self._precreate_progress_rows()
        self._resize_and_center()
        self.lift()
        self.focus_force()
        self._timer_id = self.after(100, self._check_progress)
        logging_debug(_("Compass calibration progress popup created and polling scheduled."))

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

    def _load_expected_compass_ids(self) -> list[int]:
        """Ask the data model which compasses are expected before telemetry starts arriving."""
        try:
            raw_compass_ids = self.model.get_active_compass_ids()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logging_debug(
                _("Compass calibration popup could not query expected compasses from the model: %(error)s"),
                {"error": str(exc)},
            )
            return []

        if not isinstance(raw_compass_ids, (list, tuple, set)):
            logging_debug(
                _("Compass calibration popup received unexpected compass list type %(type)s; waiting for telemetry."),
                {"type": type(raw_compass_ids).__name__},
            )
            return []

        compass_ids = sorted({int(compass_id) for compass_id in raw_compass_ids})
        logging_debug(_("Compass calibration popup expects compass ids: %(compasses)s"), {"compasses": compass_ids})
        return compass_ids

    def _create_progress_row(self, compass_id: int) -> ttk.Progressbar:
        """Create the visual row for a compass if it does not already exist."""
        if compass_id not in self.progress_bars:
            row = ttk.Frame(self.rows_container)
            row.pack(fill="x", pady=8)
            ttk.Label(
                row,
                text=_("Compass {compass_id}").format(compass_id=compass_id),
                width=10,
                font=("TkDefaultFont", 11, "bold"),
            ).pack(side="left")
            progress_bar = ttk.Progressbar(row, orient="horizontal", length=320, mode="indeterminate", maximum=100)
            progress_bar.pack(side="left", expand=True, fill="x", padx=10)
            progress_bar.start(10)

            self.progress_bars[compass_id] = progress_bar
            self.completion_status[compass_id] = False
            logging_debug(_("Compass calibration progress bar created for compass %(compass_id)s"), {"compass_id": compass_id})
            self.update_idletasks()
            self._resize_and_center()

        return self.progress_bars[compass_id]

    def _precreate_progress_rows(self) -> None:
        """Create placeholder rows for the compasses the data model already knows about."""
        if not self._expected_compass_ids:
            logging_debug(
                _("Compass calibration popup has no known active compasses yet; waiting for telemetry to discover them.")
            )
            return

        for compass_id in self._expected_compass_ids:
            self._create_progress_row(compass_id)

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

    def _check_progress(self) -> None:  # noqa: PLR0915  # pylint: disable=too-many-branches, too-many-statements
        data_list = self.model.get_progress()
        # logging_debug(_("Compass calibration progress poll returned %(count)d updates"), {"count": len(data_list)})

        if not data_list:
            self._polls_without_updates += 1
            if self._polls_without_updates == 50 and not self._no_telemetry_warning_emitted:
                self._no_telemetry_warning_emitted = True
                logging_warning(
                    _(
                        "No compass calibration telemetry has arrived after %(polls)d polls. "
                        "The FC may still be waiting for vehicle movement, or the calibration may not have started."
                    ),
                    {"polls": self._polls_without_updates},
                )
            # logging_debug(_("Compass calibration progress poll found no updates; rescheduling in 100 ms."))
            self._timer_id = self.after(100, self._check_progress)
            return

        self._polls_without_updates = 0
        self._no_telemetry_warning_emitted = False
        for raw_data in data_list:
            data: dict[str, Any] = cast("dict", raw_data)
            cid_raw = data.get("compass_id")
            cid = int(cid_raw) if cid_raw is not None else 0
            logging_debug(
                _("Compass calibration update received for compass %(compass_id)s: type=%(update_type)s"),
                {"compass_id": cid_raw, "update_type": data.get("type")},
            )

            if data["type"] == "STATUS_TEXT":
                status_text = str(data.get("text", "")).strip()
                if status_text:
                    self.hint_label.configure(text=status_text)
                if "Compass calibrated requires reboot" in status_text and cid_raw is None:
                    for compass_id, progress_bar in self.progress_bars.items():
                        progress_bar.stop()
                        progress_bar.configure(mode="determinate")
                        progress_bar["maximum"] = 100
                        progress_bar["value"] = 100
                        progress_bar.configure(style="Done.Horizontal.TProgressbar")
                        progress_bar.update_idletasks()
                        self.completion_status[compass_id] = True
                    logging_debug(_("Compass calibration completion inferred from generic status text."))
                    continue
                if cid_raw is None:
                    continue
                # Some ArduPilot builds emit calibration feedback as STATUSTEXT
                # before any MAG_CAL_PROGRESS packet arrives. Create the row as
                # soon as we know which compass is talking so the user sees a
                # visible progress indicator instead of only the hint text.
                progress_bar = self._create_progress_row(cid)
                if "Compass calibrated requires reboot" in status_text:
                    progress_bar.stop()
                    progress_bar.configure(mode="determinate")
                    progress_bar["maximum"] = 100
                    progress_bar["value"] = 100
                    progress_bar.configure(style="Done.Horizontal.TProgressbar")
                    progress_bar.update_idletasks()
                    self.completion_status[cid] = True
                    logging_debug(
                        _("Compass calibration completion inferred from status text for compass %(compass_id)s"),
                        {"compass_id": cid_raw},
                    )
                continue

            progress_bar = self._create_progress_row(cid)

            if data["type"] == "PROGRESS":
                progress_bar.stop()
                progress_bar.configure(mode="determinate")
                pct = data.get("completion_pct", 0)
                progress_bar["value"] = int(pct)
                logging_debug(
                    _("Compass calibration progress bar updated for compass %(compass_id)s to %(pct)s%%"),
                    {"compass_id": cid_raw, "pct": int(pct)},
                )

            elif data["type"] == "REPORT":
                # Only mark as done if the calibration was successful (status 4 = MAG_CAL_SUCCESS)
                progress_bar.stop()
                progress_bar.configure(mode="determinate")
                if data.get("status") == 4 or data.get("saved"):
                    progress_bar["maximum"] = 100
                    progress_bar["value"] = 100
                    progress_bar.configure(style="Done.Horizontal.TProgressbar")
                    progress_bar.update_idletasks()
                    self.completion_status[cid] = True
                    logging_debug(_("Compass calibration completed for compass %(compass_id)s"), {"compass_id": cid_raw})
                else:
                    # The calibration failed; try to cancel the session before closing the popup.
                    logging_debug(
                        _("Compass calibration failed for compass %(compass_id)s; attempting cancel."), {"compass_id": cid_raw}
                    )
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
                        logging_debug(
                            _("Compass calibration cancel failed after report failure: %(error)s"), {"error": error_msg}
                        )
                        self._timer_id = self.after(100, self._check_progress)
                    return

        if self.completion_status and all(self.completion_status.values()):
            if self._timer_id:
                self.after_cancel(self._timer_id)
            self.model.finish_calibration()
            logging_debug(_("Compass calibration finished for all compasses; closing popup."))
            messagebox.showinfo(_("Calibration Complete"), _("All compasses successfully calibrated and saved!"), parent=self)
            self.destroy()
        else:
            logging_debug(_("Compass calibration still in progress; scheduling next poll in 100 ms."))
            self._timer_id = self.after(100, self._check_progress)

    def _on_cancel(self) -> None:
        logging_debug(_("Compass calibration cancel button clicked."))
        self._stop_polling()
        success, error_msg = self.model.cancel_calibration()
        if success:
            self.model.finish_calibration()
            logging_debug(_("Compass calibration cancel accepted; closing popup."))
            messagebox.showinfo(_("Cancelled"), _("Compass calibration was cancelled."), parent=self)
            self.destroy()
            return

        messagebox.showerror(_("Failed to Cancel"), error_msg, parent=self)
        logging_debug(_("Compass calibration cancel rejected: %(error)s"), {"error": error_msg})
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
        logging_debug(_("Compass calibration start button clicked."))
        parent = cast("tk.Widget", self.winfo_toplevel())
        self._instructions_popup = CompassCalibrationInstructionsPopup(parent, self._begin_calibration)

    def _begin_calibration(self) -> None:
        logging_debug(_("Compass calibration instructions accepted; starting calibration."))
        success, error_msg = self.model.start_calibration()
        if success:
            logging_debug(_("Compass calibration start succeeded; opening progress popup."))
            parent = cast("tk.Widget", self.winfo_toplevel())
            self._calibration_popup = CompassCalibrationPopup(parent, self.model)
        else:
            logging_debug(_("Compass calibration start failed: %(error)s"), {"error": error_msg})
            messagebox.showerror(_("Failed to Start"), error_msg, parent=self)


def _create_compass_calibration_view(
    parent: tk.Frame | ttk.Frame,
    model: object,
    base_window: object,
) -> CompassCalibrationView:
    return CompassCalibrationView(parent, cast("CompassCalibrationDataModel", model), cast("BaseWindow", base_window))


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
        showerror(_("Error"), _("Failed to start compass calibration: %(error)s") % {"error": e})
    finally:
        if state.flight_controller:
            state.flight_controller.disconnect()  # Disconnect from the flight controller


if __name__ == "__main__":  # pragma: no cover
    main()
