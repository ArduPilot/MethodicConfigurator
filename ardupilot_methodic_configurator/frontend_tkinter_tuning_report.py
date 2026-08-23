"""
Interactive parameter transition graph, sourced from tuning_report.csv.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-FileCopyrightText: 2026 Omkar Sarkar <omkarsarkar24@gmail.com>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import math
import tkinter as tk
from tkinter import ttk
from typing import Any

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.log_analysis.data_model_tuning_report import TuningReport, load_tuning_report


class TuningReportWindow(BaseWindow):
    """Interactive multi-series chart of parameter transitions across tuning steps."""

    def __init__(self, root_tk: tk.Tk | tk.Toplevel, csv_path: str) -> None:
        super().__init__(root_tk)
        self.report: TuningReport = load_tuning_report(csv_path)
        self.check_vars: dict[str, tk.BooleanVar] = {name: tk.BooleanVar(value=False) for name in self.report.values}
        self.hover_data: list[tuple[Any, Any, Any]] = []

        self.root.title(_("Tuning Parameter Graph"))
        self.root.geometry(self.calculate_scaled_geometry(1150, 750))
        self.center_window(self.root, root_tk)
        self.root.resizable(width=True, height=True)

        container = ttk.Frame(self.main_frame)
        container.pack(fill=tk.BOTH, expand=True)

        self._build_left_panel(container)
        self._build_chart_panel(container)

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        left = ttk.Frame(parent, width=280)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(8, 4), pady=8)
        left.pack_propagate(False)  # noqa: FBT003

        ttk.Label(left, text=_("Parameters:"), font=("TkDefaultFont", 11, "bold")).pack(anchor=tk.W, pady=(0, 4))
        scroll_container = ScrollFrame(left)
        scroll_container.pack(fill=tk.BOTH, expand=True)
        param_list = scroll_container.view_port

        last_prefix = None
        for param_name in sorted(self.report.values):
            prefix = param_name.split("_")[0]
            if prefix != last_prefix:
                ttk.Label(param_list, text=prefix, foreground="gray", font=("TkDefaultFont", 10, "bold")).pack(
                    anchor=tk.W, pady=(6, 0)
                )
                last_prefix = prefix
            ttk.Checkbutton(
                param_list,
                text=param_name,
                variable=self.check_vars[param_name],
                command=self._redraw,
            ).pack(anchor=tk.W)

    def _build_chart_panel(self, parent: ttk.Frame) -> None:
        right_scroll = ScrollFrame(parent)
        right_scroll.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 8), pady=8)

        self.figure = Figure(figsize=(7, 6), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=right_scroll.view_port)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.canvas.mpl_connect("motion_notify_event", self._on_hover)

        self._redraw()

    def _redraw(self) -> None:
        self.figure.clear()
        self.hover_data.clear()

        selected_params = [name for name, var in self.check_vars.items() if var.get()]
        num_plots = len(selected_params)

        if num_plots == 0:
            self.figure.set_figheight(6)
            self.canvas.get_tk_widget().configure(height=int(6 * self.figure.dpi))
            ax = self.figure.add_subplot(111)
            ax.text(
                0.5,
                0.5,
                _("Select one or more parameters to plot transitions"),
                ha="center",
                va="center",
                color="#555555",
                fontsize=12,
                transform=ax.transAxes,
            )
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            self.canvas.draw()
            self.canvas.get_tk_widget().update_idletasks()
            return

        calc_height = max(6.0, num_plots * 1.5)
        self.figure.set_figheight(calc_height)
        self.canvas.get_tk_widget().configure(height=int(calc_height * self.figure.dpi))

        axes = self.figure.subplots(nrows=num_plots, ncols=1, sharex=True, squeeze=False)
        flat_axes = [ax[0] for ax in axes]

        x_positions = list(range(len(self.report.steps)))

        for idx, (param_name, ax) in enumerate(zip(selected_params, flat_axes, strict=True)):
            raw_y = self.report.values[param_name]
            cleaned_y = [math.nan if v is None else v for v in raw_y]

            # Keep a reference to the plotted line
            (line,) = ax.plot(
                x_positions,
                cleaned_y,
                marker="o",
                markersize=6,
                linewidth=2.0,
                color="#2b5c8f",
            )

            ax.set_ylabel(param_name, fontsize=10, rotation=0, ha="right", va="center")
            ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.7, color="#aaaaaa")  # noqa: FBT003
            ax.tick_params(axis="both", labelsize=9)

            # Create an invisible annotation box for this subplot
            annot = ax.annotate(
                "",
                xy=(0, 0),
                xytext=(10, 10),
                textcoords="offset points",
                bbox={"boxstyle": "round,pad=0.4", "fc": "#ffffff", "ec": "#aaaaaa", "lw": 1},
                fontsize=9,
                zorder=10,
            )
            annot.set_visible(False)

            # Store the line, axis, and annotation for the hover event reader
            self.hover_data.append((line, ax, annot))

            if idx == num_plots - 1:
                ax.set_xticks(x_positions)
                ax.set_xticklabels(self.report.steps, rotation=45, ha="right", fontsize=10)

        self.figure.align_ylabels(flat_axes)
        self.figure.subplots_adjust(hspace=0.1)
        self.figure.tight_layout()
        self.canvas.draw()
        self.canvas.get_tk_widget().update_idletasks()

    def _on_hover(self, event: Any) -> None:  # noqa: ANN401
        """Triggered on mouse movement to display exact point values."""
        # Do nothing if the mouse isn't inside a plot area
        if not event.inaxes:
            return

        redraw_needed = False

        for line, ax, annot in self.hover_data:
            if event.inaxes == ax:
                # Check if the mouse coordinates intersect with our plotted line/markers
                contains, ind = line.contains(event)
                if contains:
                    # Extract exact coordinates of the hovered point
                    index = ind["ind"][0]
                    x, y = line.get_data()
                    x_val, y_val = x[index], y[index]

                    annot.xy = (x_val, y_val)
                    step_name = self.report.steps[int(x_val)]

                    text = f"Step: {step_name}\nValue: {y_val}"

                    # Only update and redraw if the tooltip is new or changed
                    if not annot.get_visible() or annot.get_text() != text:
                        annot.set_text(text)
                        annot.set_visible(True)
                        redraw_needed = True
                elif annot.get_visible():
                    annot.set_visible(False)
                    redraw_needed = True
            # Hide annotations in subplots the mouse is not currently hovering over
            elif annot.get_visible():
                annot.set_visible(False)
                redraw_needed = True

        if redraw_needed:
            self.canvas.draw_idle()

    def run(self) -> None:
        self.root.mainloop()
