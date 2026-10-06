"""
GUI for RC calibration plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import ArgumentParser, Namespace
from collections.abc import Callable
from contextlib import suppress
from functools import partial
from logging import debug as logging_debug
from logging import error as logging_error
from logging import warning as logging_warning
from math import isfinite
from time import monotonic
from tkinter import ttk
from tkinter.messagebox import showerror
from typing import Any, Literal

from PIL import ImageTk

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_calibration_popup_base import CalibrationPopupBase
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip
from ardupilot_methodic_configurator.plugins.data_model_rc_calibration import RC_STICK_MODES, RCCalibrationDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_helpers import (
    begin_calibration_navigation_lock,
    end_calibration_navigation_lock,
    refresh_parameter_editor_table,
    start_calibration_with_navigation_lock,
)
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_RC_CALIBRATION
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory
from ardupilot_methodic_configurator.plugins.renderer_3d_quadcopter import QuadcopterRenderer

_RC_DISPLAY_MIN_PWM = 800
_RC_DISPLAY_MAX_PWM = 2200
_RC_CHANNEL_COUNT = 16
_RC_STICK_SQUARE_SIZE = 126
_RC_CHANNEL_BAR_WIDTH = 200
_RC_MARKER_COLORS = {"min": "green", "trim": "blue", "max": "red"}
_RC_FRAME_PADDING = 4


class RCCraftPreview(ttk.LabelFrame):  # pylint: disable=too-many-ancestors,too-many-instance-attributes
    """Shared RC-driven craft preview with proportional lean, yaw rate and throttle lift."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, text=_("Live monitor"), padding=_RC_FRAME_PADDING)
        self.renderer = QuadcopterRenderer(width=360, height=200)
        self._axes = dict.fromkeys(("roll", "pitch", "yaw", "throttle"), 0.0)
        self._heading = 0.0
        self._last_frame_time = monotonic()
        self._last_rc_time: float | None = None
        self._channel_count = 0
        self.status_label = ttk.Label(self, text=_("No RC telemetry"), foreground="gray")
        self.status_label.pack(anchor="w")
        self.image_label = ttk.Label(self)
        self.image_label.pack(pady=5)
        ttk.Label(self, text=_("RC input preview — not measured attitude."), wraplength=360).pack()
        show_tooltip(
            self.image_label,
            _(
                "Roll and pitch tilt the example craft; yaw turns it while held; throttle raises or lowers it. "
                "Uses staged RC mapping, calibration and reversal. No vehicle movement is commanded."
            ),
        )
        self.update_telemetry({})

    def update_telemetry(self, telemetry: dict[str, Any]) -> None:
        """Render one polling frame; retain RC inputs on heartbeat and stop yaw after telemetry becomes stale."""
        now = monotonic()
        elapsed = max(0.0, min(0.25, now - self._last_frame_time))
        self._last_frame_time = now
        for axis in self._axes:
            value = telemetry.get(axis)
            if isinstance(value, (int, float)) and isfinite(value):
                self._axes[axis] = max(-1.0, min(1.0, value / 1000))
        if "channels" in telemetry:
            self._channel_count = sum(channel.get("value") is not None for channel in telemetry["channels"])
            self._last_rc_time = now if self._channel_count else None
        live = self._last_rc_time is not None and now - self._last_rc_time <= 0.5
        if live and abs(self._axes["yaw"]) > 0.04:
            self._heading = (self._heading + self._axes["yaw"] * 120 * elapsed) % 360
        self.status_label.configure(
            text=_("%(count)d channels live") % {"count": self._channel_count} if live else _("No RC telemetry"),
            foreground="green" if live else "gray",
        )
        image = self.renderer.render(self._axes["roll"], self._axes["pitch"], self._heading, (self._axes["throttle"] + 1) / 2)
        self.image_label.image = ImageTk.PhotoImage(image, master=self)  # type: ignore[attr-defined]
        self.image_label.configure(image=self.image_label.image)  # type: ignore[attr-defined]


class RCStickPreview(ttk.LabelFrame):  # pylint: disable=too-many-ancestors,too-many-instance-attributes
    """Show two white transmitter gimbals with red stick-position circles."""

    def __init__(
        self,
        parent: tk.Misc,
        model: RCCalibrationDataModel | None = None,
        on_parameters_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, text=_("Remote controller stick preview"), padding=_RC_FRAME_PADDING)
        self._model = model
        self._on_parameters_changed = on_parameters_changed
        self._axes: dict[str, float] = {}
        mapping_mode = model.get_mapping_mode() if model else 2
        self._mode = tk.IntVar(self, value=mapping_mode or 2)
        self._selected_mode = tk.StringVar(self, value=str(mapping_mode or _("Custom")))
        mode_row = ttk.Frame(self)
        mode_row.pack(fill="x", pady=(0, 6))
        ttk.Label(mode_row, text=_("RC mapping mode:")).pack(side="left")
        self.mode_selector = ttk.Combobox(
            mode_row,
            textvariable=self._selected_mode,
            values=tuple(str(mode) for mode in RC_STICK_MODES),
            state="readonly",
            width=8,
        )
        self.mode_selector.pack(side="left", padx=8)
        self.mode_selector.bind("<<ComboboxSelected>>", self._on_mode_changed)
        show_tooltip(
            self.mode_selector,
            _(
                "Stage RCMAP_ROLL/PITCH/THROTTLE/YAW for Mode 1-4; only parameter upload writes to the controller. "
                "Presets assume right horizontal CH1, right vertical CH2, left vertical CH3, left horizontal CH4. "
                "Verify the channel bars against your transmitter before uploading. Reboot after uploading mapping changes."
            ),
        )
        self._mapping_status = ttk.Label(self, wraplength=380)
        self._mapping_status.pack(fill="x", pady=(0, 6))
        if model and model.get_mapping_mode() is None:
            self._mapping_status.configure(text=_("Custom RCMAP mapping retained. Select a preset only to change it."))
        gimbals = ttk.Frame(self)
        gimbals.pack()
        self._canvases: list[tk.Canvas] = []
        self._axis_labels: list[ttk.Label] = []
        for column in range(2):
            canvas = tk.Canvas(
                gimbals,
                width=_RC_STICK_SQUARE_SIZE,
                height=_RC_STICK_SQUARE_SIZE,
                background="white",
                borderwidth=0,
                highlightthickness=0,
            )
            canvas.grid(row=0, column=column, padx=8)
            canvas.bind("<Configure>", self._on_resize)
            self._canvases.append(canvas)
            label = ttk.Label(gimbals)
            label.grid(row=1, column=column, pady=(4, 0))
            self._axis_labels.append(label)
            show_tooltip(canvas, _("The red circle shows the stick position; centered sticks appear in the square center."))
        self._draw_sticks()

    def update_axes(self, telemetry: dict[str, Any]) -> None:
        """Retain the latest axis sample and redraw both sticks."""
        if self._model is not None:
            mapping_mode = self._model.get_mapping_mode()
            self._selected_mode.set(str(mapping_mode or _("Custom")))
            if mapping_mode is not None:
                self._mode.set(mapping_mode)
        for axis in ("roll", "pitch", "throttle", "yaw"):
            value = telemetry.get(axis)
            if isinstance(value, (int, float)) and isfinite(value):
                self._axes[axis] = float(value)
        self._draw_sticks()

    def _on_mode_changed(self, _event: tk.Event) -> None:
        """Stage the mapping and immediately redraw the retained raw sample without FC writes."""
        mode = int(self._selected_mode.get())
        if self._model is not None:
            success, message = self._model.set_mapping_mode(mode)
            self._mapping_status.configure(text=message, foreground="green" if success else "red")
            if not success:
                self._selected_mode.set(str(self._model.get_mapping_mode() or _("Custom")))
                return
            if self._on_parameters_changed:
                self._on_parameters_changed()
            self._axes.update(self._model.get_preview_axes())
        self._mode.set(mode)
        self._draw_sticks()

    def _on_resize(self, _event: tk.Event) -> None:
        """Preserve square gimbals and the circle-to-square ratio after layout."""
        self._draw_sticks()

    def _draw_sticks(self) -> None:
        axis_names = {"roll": _("ROLL"), "pitch": _("PITCH"), "throttle": _("THROTTLE"), "yaw": _("YAW")}
        positions = RCCalibrationDataModel.stick_positions(self._axes, self._mode.get())
        for index, (horizontal, vertical) in enumerate(positions):
            canvas = self._canvases[index]
            # These canvases are fixed squares; leave any excess allocated space around the square.
            size = int(canvas.cget("width"))
            left = max(0, (canvas.winfo_width() - size) / 2)
            top = max(0, (canvas.winfo_height() - size) / 2)
            radius = size / 24  # Diameter is exactly 1/12 of the square side.
            travel = size / 2 - radius
            center_x = left + size / 2 + horizontal * travel
            center_y = top + size / 2 - vertical * travel
            canvas.delete("all")
            canvas.create_rectangle(left, top, left + size, top + size, fill="white", outline="#999999", tags="gimbal")
            canvas.create_oval(
                center_x - radius,
                center_y - radius,
                center_x + radius,
                center_y + radius,
                fill="red",
                outline="",
                tags="stick",
            )
            self._axis_labels[index].configure(
                text=f"{axis_names[RC_STICK_MODES[self._mode.get()][index][0]]} ↔ / "
                f"{axis_names[RC_STICK_MODES[self._mode.get()][index][1]]} ↕"
            )


class RCChannelBars(ttk.LabelFrame):  # pylint: disable=too-many-ancestors,too-many-instance-attributes
    """Display PWM values, configurable channel functions, and calibration markers for all RC inputs."""

    def __init__(
        self,
        parent: tk.Misc,
        model: RCCalibrationDataModel | None = None,
        on_parameters_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, text=_("Channels"), padding=_RC_FRAME_PADDING)
        self._model = model
        self._on_parameters_changed = on_parameters_changed
        self._value_labels: dict[int, ttk.Label] = {}
        self._bar_canvases: dict[int, tk.Canvas] = {}
        self._channel_values: dict[int, dict[str, int | None]] = {}
        self._function_labels: dict[int, ttk.Label] = {}
        self._option_selectors: dict[int, ttk.Combobox] = {}
        self._option_display_values: dict[int, dict[str, str]] = {}
        self._channel_rows: dict[int, ttk.Frame] = {}
        self._canvas_background = ttk.Style(self).lookup("TFrame", "background") or "white"

        self._header = ttk.Frame(self)
        self._header.pack(fill="x")
        ttk.Label(self._header, text=_("Channel"), width=6, anchor="center").pack(side="left")
        ttk.Label(self._header, text=_("Function"), width=16, anchor="center").pack(side="left")
        ttk.Label(self._header, text=_("PWM"), width=9, anchor="center").pack(side="left", padx=(0, 8))
        self._feedback_label = ttk.Label(self)
        channel_info = model.get_channel_calibration() if model else []

        for channel_number in range(1, _RC_CHANNEL_COUNT + 1):
            row = ttk.Frame(self)
            row.pack(fill="x", pady=1)
            self._channel_rows[channel_number] = row

            ttk.Label(row, text=f"CH{channel_number}", width=6, font=("TkDefaultFont", 9, "bold")).pack(side="left")
            function_label = ttk.Label(row, width=16, anchor="center")
            function_label.pack(side="left", padx=(0, 4))
            self._function_labels[channel_number] = function_label

            value_label = ttk.Label(row, text=_("No Data"), width=9, anchor="e")
            value_label.pack(side="left", padx=(0, 8), pady=(16, 0) if channel_number == 1 else 0)
            self._value_labels[channel_number] = value_label

            canvas = tk.Canvas(
                row,
                height=38 if channel_number == 1 else 24,
                width=_RC_CHANNEL_BAR_WIDTH,
                background=self._canvas_background,
                borderwidth=0,
                highlightthickness=0,
            )
            canvas.pack(side="left", fill="x", expand=True)
            canvas.bind("<Configure>", self._on_channel_canvas_resize)
            self._bar_canvases[channel_number] = canvas
            self._channel_values[channel_number] = {"value": None, "min": 1000, "max": 2000, "trim": 1500}
            self._draw_channel(channel_number)
            show_tooltip(
                canvas,
                _(
                    "Green MIN, blue TRIM and red MAX markers show calibration. "
                    "MIN/MAX track observed extremes during calibration. "
                    "Missing calibration parameters use display defaults of 1000/2000/1500 µs."
                ),
            )
        if model:
            self.update_channels(channel_info)

    def update_channels(self, channels: list[dict[str, Any]]) -> None:
        """Update the 16 persistent rows from the latest model telemetry."""
        channels_by_name = {channel.get("name"): channel for channel in channels}
        for channel_number in range(1, _RC_CHANNEL_COUNT + 1):
            channel = channels_by_name.get(f"CH{channel_number}", {})
            self._update_channel_function(channel_number, channel)
            value = self._optional_pwm_value(channel.get("value"))
            minimum = self._optional_pwm_value(channel.get("min"))
            maximum = self._optional_pwm_value(channel.get("max"))
            trim = self._optional_pwm_value(channel.get("trim"))
            self._channel_values[channel_number] = {
                "value": value,
                "min": minimum if minimum is not None else 1000,
                "max": maximum if maximum is not None else 2000,
                "trim": trim if trim is not None else 1500,
            }
            self._value_labels[channel_number].configure(text=f"{value} µs" if value is not None else _("No Data"))
            self._draw_channel(channel_number)

    def _update_channel_function(self, channel_number: int, channel: dict[str, Any]) -> None:
        """Reconcile the function control with the model's current editability."""
        row = self._channel_rows[channel_number]
        if channel.get("function_editable", False) and self._model is not None:
            function_label = self._function_labels.pop(channel_number, None)
            if function_label is not None:
                function_label.destroy()
            selector = self._option_selectors.get(channel_number)
            if selector is None:
                selector = ttk.Combobox(row, state="disabled", width=16)
                selector.pack(side="left", padx=(0, 4), before=self._value_labels[channel_number])
                selector.bind("<<ComboboxSelected>>", partial(self._on_option_selected, channel_number))
                self._option_selectors[channel_number] = selector
                show_tooltip(
                    selector,
                    _("Select this channel's RCx_OPTION function. Changes are staged until parameter upload."),
                )
            self._update_option_selector(channel_number, selector, channel)
        else:
            selector = self._option_selectors.pop(channel_number, None)
            if selector is not None:
                selector.destroy()
            self._option_display_values.pop(channel_number, None)
            function_label = self._function_labels.get(channel_number)
            if function_label is None:
                function_label = ttk.Label(row, width=16, anchor="center")
                function_label.pack(side="left", padx=(0, 4), before=self._value_labels[channel_number])
                self._function_labels[channel_number] = function_label
            function_label.configure(text=channel.get("function") or channel.get("option_label", ""))

    def _update_option_selector(self, channel_number: int, selector: ttk.Combobox, channel: dict[str, Any]) -> None:
        """Fill a channel selector with loaded ArduPilot metadata while retaining the active choice."""
        choices = channel.get("option_choices", {})
        display_values: dict[str, str] = {}
        if isinstance(choices, dict):
            for key, description in choices.items():
                try:
                    option = int(float(key))
                except (TypeError, ValueError):
                    continue
                display_values[f"{option}: {description}"] = str(option)
        self._option_display_values[channel_number] = display_values
        selected_key = self._option_value_key(channel.get("option_value"))
        selected_display = next((display for display, value in display_values.items() if value == selected_key), "")
        if selected_key and not selected_display:
            selected_display = f"{selected_key}: {_('Unknown option')}"
            display_values[selected_display] = selected_key
        available_values = tuple(display_values)
        if tuple(selector.cget("values")) != available_values:
            selector.configure(values=available_values)
        state = "readonly" if channel.get("function_editable", False) and choices and self._model is not None else "disabled"
        if str(selector.cget("state")) != state:
            selector.configure(state=state)
        if selector.get() != selected_display and selector.focus_get() is not selector:
            selector.set(selected_display)

    def _on_option_selected(self, channel_number: int, _event: tk.Event) -> None:
        """Stage the selected RCx_OPTION value and refresh the visible New values."""
        selector = self._option_selectors.get(channel_number)
        if selector is None:
            return
        option_value = self._option_display_values[channel_number].get(selector.get())
        if option_value is None or self._model is None:
            return
        success, message = self._model.set_channel_option(channel_number, option_value)
        self._feedback_label.configure(text=message, foreground="green" if success else "red")
        self._feedback_label.pack(fill="x", before=self._header)
        if success and self._on_parameters_changed:
            self._on_parameters_changed()
        self.update_channels(self._model.get_channel_calibration())

    @staticmethod
    def _option_value_key(value: object) -> str:
        """Format a finite integral enum value as a key from loaded parameter metadata."""
        if isinstance(value, (int, float)) and isfinite(value) and value == int(value):
            return str(int(value))
        return ""

    def update_calibration(self, channels: list[dict[str, Any]]) -> None:
        """Refresh marker positions without discarding the last live PWM values."""
        self.update_channels(
            [{**channel, "value": self._channel_values[number]["value"]} for number, channel in enumerate(channels, start=1)]
        )

    def _on_channel_canvas_resize(self, event: tk.Event) -> None:
        """Redraw the channel whose canvas was resized."""
        for channel_number, canvas in self._bar_canvases.items():
            if canvas is event.widget:
                self._draw_channel(channel_number, event.width)
                return

    def _draw_channel(self, channel_number: int, width: int | None = None) -> None:
        """Paint green MIN, blue TRIM and red MAX markers; labels appear only above channel 1."""
        canvas = self._bar_canvases[channel_number]
        canvas.delete("all")
        canvas_width = width if width is not None else canvas.winfo_width()
        canvas_width = canvas_width if canvas_width > 1 else int(canvas.cget("width"))
        left = 1
        right = canvas_width - 1
        bar_top = 18 if channel_number == 1 else 3
        canvas.create_rectangle(left, bar_top, right, bar_top + 16, fill="#d6d6d6", outline="", tags=("track",))

        channel = self._channel_values[channel_number]
        value = channel["value"]
        if value is not None:
            value_x = self._pwm_to_x(value, canvas_width)
            canvas.create_rectangle(left, bar_top, value_x, bar_top + 16, fill="#4b91c5", outline="", tags=("live_value",))

        for marker_name, marker_color in _RC_MARKER_COLORS.items():
            marker_value = channel[marker_name]
            if marker_value is not None:
                marker_x = self._pwm_to_x(marker_value, canvas_width)
                canvas.create_line(
                    marker_x,
                    bar_top - 2,
                    marker_x,
                    bar_top + 18,
                    fill=marker_color,
                    width=3,
                    tags=(f"{marker_name}_marker", "calibration_marker"),
                )
                if channel_number == 1:
                    canvas.create_text(
                        marker_x,
                        8,
                        text=marker_name.upper(),
                        fill=marker_color,
                        anchor=self._marker_label_anchor(marker_name),
                        font=("TkDefaultFont", 7),
                        tags=(f"{marker_name}_label",),
                    )

    @staticmethod
    def _marker_label_anchor(marker_name: str) -> Literal["w", "e", "center"]:
        """Keep the outer labels inside the canvas even at the track endpoints."""
        return "w" if marker_name == "min" else "e" if marker_name == "max" else "center"

    @staticmethod
    def _optional_pwm_value(value: object) -> int | None:
        """Accept finite numeric PWM values, including float-valued parameter cache entries."""
        return round(value) if isinstance(value, (int, float)) and isfinite(value) and 0 < value < 65535 else None

    @staticmethod
    def _pwm_to_x(value: int, width: int) -> int:
        """Map a PWM value to the bar's horizontal position, clamped to 800-2200 µs."""
        clamped_value = max(_RC_DISPLAY_MIN_PWM, min(_RC_DISPLAY_MAX_PWM, value))
        fraction = (clamped_value - _RC_DISPLAY_MIN_PWM) / (_RC_DISPLAY_MAX_PWM - _RC_DISPLAY_MIN_PWM)
        return 1 + round(fraction * (width - 2))


class RCCalibrationPopup(CalibrationPopupBase["RCCalibrationDataModel"]):
    """A modern, borderless popup window with a custom draggable title bar for RC monitoring."""

    _MIN_WIDTH = 600
    _MIN_HEIGHT = 500

    def __init__(self, parent: tk.Widget, model: RCCalibrationDataModel) -> None:
        super().__init__(parent, model)

        self._setup_style()
        self._setup_ui()
        self._resize_and_center()
        self.root.lift()
        self.root.focus_force()
        self._timer_id = self.root.after(100, self._check_telemetry)
        logging_debug(_("RC calibration progress popup created and polling scheduled."))

    def _setup_ui(self) -> None:
        content_frame = self._create_framed_ui(_("Live Monitor"))
        content_frame.pack_configure(padx=_RC_FRAME_PADDING, pady=_RC_FRAME_PADDING)
        self._scroll_frame = ScrollFrame(content_frame)
        self._scroll_frame.pack(fill="both", expand=True)
        # Use the explicit outer margin instead of ScrollFrame's additional inset.
        self._scroll_frame.canvas.coords(self._scroll_frame.canvas_window, 0, 0)
        self._scroll_frame.on_frame_configure(None)
        self._scroll_frame.canvas.xview_moveto(0)
        self._scroll_frame.scroll_to_top()
        content_frame = self._scroll_frame.view_port

        self.craft_preview = RCCraftPreview(content_frame)
        self.craft_preview.pack(fill="x", pady=(0, _RC_FRAME_PADDING))

        self.stick_preview = RCStickPreview(content_frame, self.model, self._refresh_preview)
        self.stick_preview.pack(fill="x", pady=(0, _RC_FRAME_PADDING))

        self.channel_bars = RCChannelBars(content_frame, self.model, self._refresh_preview)
        self.channel_bars.pack(fill="x", expand=True, pady=(0, _RC_FRAME_PADDING))

    def _refresh_preview(self) -> None:
        """Refresh channel functions and preview after staging an RC mapping or auxiliary option."""
        axes = self.model.get_preview_axes()
        self.stick_preview.update_axes(axes)
        self.craft_preview.update_telemetry(axes)
        self.channel_bars.update_channels(self.model.get_channel_calibration())

    def _check_telemetry(self) -> None:
        telemetry = self.model.get_rc_telemetry()
        self.craft_preview.update_telemetry(telemetry)

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

        self.stick_preview.update_axes(telemetry)
        if "channels" in telemetry:
            self.channel_bars.update_channels(telemetry["channels"])

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
        self._calibration_active = False
        self._polls_without_updates = 0
        self._no_telemetry_warning_emitted = False
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
        control_frame.pack(fill="x", padx=_RC_FRAME_PADDING, pady=(_RC_FRAME_PADDING, 0))

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

        self._scroll_frame = ScrollFrame(outer_frame)
        self._scroll_frame.pack(fill="both", expand=True, padx=_RC_FRAME_PADDING, pady=_RC_FRAME_PADDING)
        # Match the documentation margin without adding ScrollFrame's default inset.
        self._scroll_frame.canvas.coords(self._scroll_frame.canvas_window, 0, 0)
        self._scroll_frame.on_frame_configure(None)
        self._scroll_frame.canvas.xview_moveto(0)
        self._scroll_frame.scroll_to_top()
        content_frame = self._scroll_frame.view_port

        self.craft_preview = RCCraftPreview(content_frame)
        self.craft_preview.pack(fill="x", pady=(0, _RC_FRAME_PADDING))

        self.stick_preview = RCStickPreview(content_frame, self.model, self._refresh_parameters)
        self.stick_preview.pack(fill="x", pady=(0, _RC_FRAME_PADDING))

        self.channel_bars = RCChannelBars(content_frame, self.model, self._refresh_parameters)
        self.channel_bars.pack(fill="x", expand=True, pady=(0, _RC_FRAME_PADDING))

    def _on_start_calibration(self) -> None:
        start_calibration_with_navigation_lock(self.base_window, self, self._start_calibration)

    def _start_calibration(self) -> bool:
        """Start collecting RC extremes with navigation already locked."""
        success, error_msg = self.model.start_calibration()
        if success:
            self._calibration_active = True
            try:
                self.channel_bars.update_calibration(self.model.get_channel_calibration())
                self._start_btn.configure(state="disabled")
                self._finish_btn.configure(state="normal")
                self._cancel_btn.configure(state="normal")
                self._status_label.configure(
                    text=_("Calibrating — move all sticks and switches to their extremes, then click Finish."),
                    foreground="blue",
                )
            except Exception:
                try:
                    self.model.cancel_calibration()
                finally:
                    self._calibration_active = False
                    for button, state in (
                        (self._start_btn, "normal"),
                        (self._finish_btn, "disabled"),
                        (self._cancel_btn, "disabled"),
                    ):
                        with suppress(tk.TclError):
                            button.configure(state=state)
                raise
        else:
            self._status_label.configure(text=error_msg, foreground="red")
        return success

    def _on_finish_calibration(self) -> None:
        # Failed staging stops collection but retains measurements for a locked retry.
        if not self._calibration_active and not begin_calibration_navigation_lock(self.base_window, self):
            return
        try:
            success, message = self.model.finish_calibration()
            if success:
                self._refresh_parameters()
            self.channel_bars.update_calibration(self.model.get_channel_calibration())
        finally:
            self._calibration_active = False
            end_calibration_navigation_lock(self.base_window, self)
        self._start_btn.configure(state="normal")
        self._finish_btn.configure(state="disabled" if success else "normal")
        self._cancel_btn.configure(state="disabled" if success else "normal")
        self._status_label.configure(
            text=message,
            foreground="green" if success else "red",
        )

    def _refresh_parameters(self) -> None:
        """Show staged edits in the existing New-value table without downloading or uploading."""
        refresh_parameter_editor_table(self.base_window)
        axes = self.model.get_preview_axes()
        self.stick_preview.update_axes(axes)
        self.craft_preview.update_telemetry(axes)
        self.channel_bars.update_channels(self.model.get_channel_calibration())

    def _on_cancel_calibration(self) -> None:
        try:
            self.model.cancel_calibration()
            self.channel_bars.update_calibration(self.model.get_channel_calibration())
        finally:
            self._calibration_active = False
            end_calibration_navigation_lock(self.base_window, self)
        self._start_btn.configure(state="normal")
        self._finish_btn.configure(state="disabled")
        self._cancel_btn.configure(state="disabled")
        self._status_label.configure(text=_("Calibration cancelled."), foreground="gray")

    def _stop_polling(self) -> None:
        if self._timer_id:
            with suppress(tk.TclError):
                self.after_cancel(self._timer_id)
            self._timer_id = None

    def _check_telemetry(self) -> None:
        telemetry = self.model.get_rc_telemetry()
        self.craft_preview.update_telemetry(telemetry)

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

        self.stick_preview.update_axes(telemetry)
        if "channels" in telemetry:
            self.channel_bars.update_channels(telemetry["channels"])

        self._timer_id = self.after(100, self._check_telemetry)

    def destroy(self) -> None:
        """Stop the polling loop before destroying the widget."""
        try:
            self._stop_polling()
            if self._calibration_active:
                self.model.cancel_calibration()
                self._calibration_active = False
        finally:
            end_calibration_navigation_lock(self.base_window, self)
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


def _create_rc_calibration_model(context: PluginModelContext) -> RCCalibrationDataModel:
    """Create the plugin data model from registered application dependencies."""
    return RCCalibrationDataModel(context.flight_controller, context.parameter_editor)


def register_rc_calibration_plugin() -> None:
    """Register the RC calibration plugin with the factory."""
    plugin_factory.register(PLUGIN_RC_CALIBRATION, _create_rc_calibration_view, _create_rc_calibration_model)


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
