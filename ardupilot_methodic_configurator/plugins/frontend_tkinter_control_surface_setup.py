"""
GUI for the plane and tilt-rotor control surface setup plugin.

The view is a notebook with one tab per setup stage:

1. Servo direction  - FBWA, move the airframe, fix SERVOx_REVERSED
2. Stick direction  - move the RC sticks, fix RCx_REVERSED
3. Trim and travel  - MANUAL, live SERVOx_TRIM/MIN/MAX with simulated stick sliders
4. Tilt rotors      - only when Q_TILT_ENABLE=1: tilt settings, forward (MANUAL) and hover (QSTABILIZE) end points

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Allister779

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Callable
from contextlib import suppress
from logging import warning as logging_warning
from tkinter import ttk
from tkinter.messagebox import showerror, showinfo, showwarning

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip
from ardupilot_methodic_configurator.plugins.data_model_control_surface_setup import (
    AIRFRAME_MOVEMENT_CHECKS,
    STICK_MOVEMENT_CHECKS,
    TILT_SETTING_PARAMETERS,
    ControlSurfaceSetupDataModel,
    ControlSurfaceSetupError,
    EndpointKind,
    PlaneMode,
    SaveResult,
    ServoChannel,
    StickAxis,
)
from ardupilot_methodic_configurator.plugins.frontend_tkinter_helpers import (
    cancel_plugin_timer,
    refresh_parameter_editor_table,
)
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_CONTROL_SURFACE_SETUP
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory
from ardupilot_methodic_configurator.plugins.plugin_protocol import PluginPauseReason

# pylint: disable=too-many-instance-attributes,too-many-ancestors

TELEMETRY_PERIOD_MS = 100
OVERRIDE_PERIOD_MS = 300  # well below the default RC_OVERRIDE_TIME of 3 s
BATTERY_PERIOD_MS = 1000
LIVE_WRITE_DELAY_MS = 150
SPINBOX_INCREMENT_PWM = 5
WRAP_LENGTH = 520


class _LiveSpinbox(ttk.Spinbox):
    """Integer spinbox that calls ``on_change`` shortly after the user stops editing."""

    def __init__(self, parent: tk.Misc, value: float, on_change: Callable[[float], None], **kwargs: float) -> None:
        self._var = tk.StringVar(value=f"{value:g}")
        super().__init__(parent, textvariable=self._var, width=7, command=self._schedule, **kwargs)  # type: ignore[arg-type]
        self._on_change = on_change
        self._pending: str | None = None
        self.bind("<Return>", lambda _event: self._fire())
        self.bind("<FocusOut>", lambda _event: self._fire())

    def _schedule(self) -> None:
        cancel_plugin_timer(self, self._pending)
        self._pending = self.after(LIVE_WRITE_DELAY_MS, self._fire)

    def _fire(self) -> None:
        cancel_plugin_timer(self, self._pending)
        self._pending = None
        try:
            value = float(self._var.get())
        except ValueError:
            showerror(_("Invalid value"), _("Please enter a number."))
            return
        self._on_change(value)

    def set_value(self, value: float) -> None:
        """Display ``value`` without triggering a write."""
        self._var.set(f"{value:g}")

    def destroy(self) -> None:
        """Cancel the pending write before the widget is destroyed."""
        cancel_plugin_timer(self, self._pending)
        self._pending = None
        super().destroy()


class ControlSurfaceSetupView(ttk.Frame):
    """Guided, live setup of plane control surfaces and tilt-rotor servos."""

    def __init__(
        self,
        parent: tk.Frame | ttk.Frame,
        model: ControlSurfaceSetupDataModel,
        base_window: BaseWindow,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        self._telemetry_timer: str | None = None
        self._override_timer: str | None = None
        self._battery_timer: str | None = None
        self._active = False
        self._pwm_labels: list[tuple[ServoChannel, ttk.Label]] = []
        self._trim_warnings: dict[int, ttk.Label] = {}
        self._endpoint_spinboxes: dict[str, _LiveSpinbox] = {}
        self._servo_reversed_vars: dict[int, tk.BooleanVar] = {}
        self._rc_reversed_vars: dict[StickAxis, tk.BooleanVar] = {}
        self._stick_scales: dict[StickAxis, tk.Scale] = {}
        self._battery_var = tk.StringVar(value=_("Checking battery voltage..."))
        self._mode_var = tk.StringVar(value="")
        self._battery_ok = False

        self._create_widgets()
        self.on_activate()

    # ------------------------------------------------------------------ layout

    def _create_widgets(self) -> None:
        status = ttk.Frame(self)
        status.pack(fill="x", pady=(0, 4))
        self._battery_label = ttk.Label(status, textvariable=self._battery_var, wraplength=WRAP_LENGTH, justify="left")
        self._battery_label.pack(anchor="w")
        ttk.Label(status, textvariable=self._mode_var).pack(anchor="w")
        ttk.Label(
            status,
            text=_("Remove the propellers before you start. The plugin switches flight modes and moves the servos."),
            foreground="red",
            wraplength=WRAP_LENGTH,
            justify="left",
        ).pack(anchor="w")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        self._create_servo_direction_tab()
        self._create_stick_direction_tab()
        self._create_trim_travel_tab()
        if self.model.is_tilt_rotor():
            self._create_tilt_rotor_tab()

    def _new_tab(self, title: str) -> ttk.Frame:
        scroll = ScrollFrame(self.notebook)
        self.notebook.add(scroll, text=title)
        return scroll.view_port

    def _mode_button(self, parent: tk.Misc, mode: PlaneMode) -> ttk.Button:
        button = ttk.Button(
            parent,
            text=_("Switch to %(mode)s") % {"mode": mode.name},
            command=lambda: self._switch_mode(mode),
        )
        show_tooltip(
            button,
            _("Command the flight controller into %(mode)s, even if it is not one of your FLTMODEx settings.")
            % {"mode": mode.name},
        )
        return button

    def _instructions(self, parent: tk.Misc, text: str) -> None:
        ttk.Label(parent, text=text, wraplength=WRAP_LENGTH, justify="left").pack(anchor="w", pady=(4, 4))

    def _check_table(self, parent: tk.Misc, checks: tuple[tuple[str, str], ...], heading: str) -> None:
        table = ttk.LabelFrame(parent, text=heading)
        table.pack(fill="x", pady=4)
        for row, (motion, expected) in enumerate(checks):
            ttk.Label(table, text=_(motion)).grid(row=row, column=0, sticky="w", padx=4)
            ttk.Label(table, text="→").grid(row=row, column=1)
            ttk.Label(table, text=_(expected)).grid(row=row, column=2, sticky="w", padx=4)

    def _pwm_label(self, parent: tk.Misc, channel: ServoChannel) -> ttk.Label:
        label = ttk.Label(parent, text="---- µs", width=9)
        show_tooltip(label, _("Live output PWM of %(name)s") % {"name": channel.display_name})
        self._pwm_labels.append((channel, label))
        return label

    def _save_button(self, parent: tk.Misc, names: Callable[[], list[str]], reason: str) -> None:
        button = ttk.Button(parent, text=_("Save to flight controller"), command=lambda: self._save(names(), reason))
        button.pack(anchor="e", pady=8)
        show_tooltip(
            button,
            _("Verify the live values on the flight controller and record them in the current configuration step."),
        )

    def _no_channels(self, parent: tk.Misc, text: str) -> None:
        ttk.Label(parent, text=text, foreground="red", wraplength=WRAP_LENGTH).pack(anchor="w", pady=8)

    def _create_servo_direction_tab(self) -> None:
        tab = self._new_tab(_("1. Servo direction"))
        self._mode_button(tab, PlaneMode.FBWA).pack(anchor="w", pady=4)
        self._instructions(
            tab,
            _(
                "With the plane in FBWA and the sticks untouched, hold it level then move it by hand. "
                "The autopilot moves the surfaces to oppose the motion. Tick Reversed on any surface "
                "that moves the wrong way; the change is applied immediately."
            ),
        )
        self._check_table(tab, AIRFRAME_MOVEMENT_CHECKS, _("Move the plane"))
        warning = self.model.rudder_mix_warning()
        if warning:
            ttk.Label(tab, text=warning, foreground="orange", wraplength=WRAP_LENGTH).pack(anchor="w")
        channels = self.model.control_surface_channels()
        if not channels:
            self._no_channels(tab, _("No servo output is assigned to a primary flight control function."))
            return
        grid = ttk.LabelFrame(tab, text=_("SERVOx_REVERSED"))
        grid.pack(fill="x", pady=4)
        for row, channel in enumerate(channels):
            ttk.Label(grid, text=channel.display_name).grid(row=row, column=0, sticky="w", padx=4)
            self._pwm_label(grid, channel).grid(row=row, column=1, padx=4)
            var = tk.BooleanVar(value=self.model.is_servo_reversed(channel))
            self._servo_reversed_vars[channel.number] = var
            check = ttk.Checkbutton(
                grid,
                text=_("Reversed"),
                variable=var,
                command=lambda ch=channel, v=var: self._live(lambda: self.model.set_servo_reversed(ch, reversed_=v.get())),  # type: ignore[misc]
            )
            check.grid(row=row, column=2, sticky="w")
            show_tooltip(check, _("Live-write %(param)s") % {"param": channel.param("REVERSED")})
        self._save_button(tab, self.model.servo_reversed_parameters, _("Control surface direction checked in FBWA"))

    def _create_stick_direction_tab(self) -> None:
        tab = self._new_tab(_("2. Stick direction"))
        self._mode_button(tab, PlaneMode.FBWA).pack(anchor="w", pady=4)
        self._instructions(
            tab,
            _(
                "Keep the plane level and move the transmitter sticks. If a surface moves the wrong way, "
                "tick Reversed on that stick's input channel. Do NOT reverse channels on the transmitter."
            ),
        )
        self._check_table(tab, STICK_MOVEMENT_CHECKS, _("Move the sticks"))
        grid = ttk.LabelFrame(tab, text=_("RCx_REVERSED"))
        grid.pack(fill="x", pady=4)
        axis_names = {StickAxis.ROLL: _("Roll"), StickAxis.PITCH: _("Pitch"), StickAxis.YAW: _("Yaw")}
        for row, axis in enumerate(StickAxis):
            rc_channel = self.model.rc_channel(axis)
            ttk.Label(grid, text=f"{axis_names[axis]} (RC{rc_channel})").grid(row=row, column=0, sticky="w", padx=4)
            var = tk.BooleanVar(value=self.model.is_rc_reversed(axis))
            self._rc_reversed_vars[axis] = var
            check = ttk.Checkbutton(
                grid,
                text=_("Reversed"),
                variable=var,
                command=lambda a=axis, v=var: self._live(lambda: self.model.set_rc_reversed(a, reversed_=v.get())),  # type: ignore[misc]
            )
            check.grid(row=row, column=1, sticky="w")
            show_tooltip(check, _("Live-write RC%(channel)d_REVERSED") % {"channel": rc_channel})
        outputs = ttk.LabelFrame(tab, text=_("Surface outputs"))
        outputs.pack(fill="x", pady=4)
        for row, channel in enumerate(self.model.control_surface_channels()):
            ttk.Label(outputs, text=channel.display_name).grid(row=row, column=0, sticky="w", padx=4)
            self._pwm_label(outputs, channel).grid(row=row, column=1, padx=4)
        self._save_button(tab, self.model.rc_reversed_parameters, _("RC stick direction checked"))

    def _create_trim_travel_tab(self) -> None:
        tab = self._new_tab(_("3. Trim and travel"))
        self._mode_button(tab, PlaneMode.MANUAL).pack(anchor="w", pady=4)
        self._instructions(
            tab,
            _(
                "In MANUAL with the sticks centred, adjust each SERVOx_TRIM until the surface is neutral. "
                "Then use the sliders to drive the surfaces to their limits and adjust SERVOx_MIN and SERVOx_MAX "
                "so they move fully without binding, or keep the defaults. Values apply immediately."
            ),
        )
        channels = self.model.control_surface_channels()
        if not channels:
            self._no_channels(tab, _("No servo output is assigned to a primary flight control function."))
            return
        grid = ttk.LabelFrame(tab, text=_("SERVOx_MIN / TRIM / MAX (µs)"))
        grid.pack(fill="x", pady=4)
        for column, heading in enumerate(("", _("Output"), "MIN", "TRIM", "MAX")):
            ttk.Label(grid, text=heading).grid(row=0, column=column, padx=4)
        for row, channel in enumerate(channels, start=1):
            ttk.Label(grid, text=channel.display_name).grid(row=row, column=0, sticky="w", padx=4)
            self._pwm_label(grid, channel).grid(row=row, column=1, padx=4)
            for column, kind in enumerate((EndpointKind.MIN, EndpointKind.TRIM, EndpointKind.MAX), start=2):
                self._endpoint_spinbox(grid, channel, kind).grid(row=row, column=column, padx=2)
            warning = ttk.Label(grid, text="", foreground="orange")
            warning.grid(row=row, column=5, sticky="w")
            self._trim_warnings[channel.number] = warning
            self._update_trim_warning(channel)

        self._create_stick_sliders(tab)

        self._save_button(
            tab,
            lambda: self.model.endpoint_parameters(
                self.model.control_surface_channels(), (EndpointKind.MIN, EndpointKind.TRIM, EndpointKind.MAX)
            ),
            _("Servo trim and travel adjusted in MANUAL"),
        )

    def _create_stick_sliders(self, tab: ttk.Frame) -> None:
        sticks = ttk.LabelFrame(tab, text=_("Simulated stick input"))
        sticks.pack(fill="x", pady=4)
        override_warning = self.model.rc_override_warning()
        if override_warning:
            ttk.Label(sticks, text=override_warning, foreground="orange", wraplength=WRAP_LENGTH).grid(
                row=0, column=0, columnspan=3, sticky="w"
            )
        axis_names = {StickAxis.ROLL: _("Roll"), StickAxis.PITCH: _("Pitch"), StickAxis.YAW: _("Yaw")}
        for row, axis in enumerate(StickAxis, start=1):
            ttk.Label(sticks, text=axis_names[axis]).grid(row=row, column=0, sticky="w", padx=4)
            scale = tk.Scale(
                sticks,
                from_=-100,
                to=100,
                orient="horizontal",
                length=260,
                resolution=1,
                command=lambda value, a=axis: self._on_stick(a, float(value)),  # type: ignore[misc]
            )
            scale.grid(row=row, column=1, sticky="ew")
            show_tooltip(scale, _("Stick deflection in percent; it stays where you leave it. Press Esc to center all."))
            scale.bind("<Escape>", lambda _event: self._center_all_sticks())
            self._stick_scales[axis] = scale
            center = ttk.Button(sticks, text=_("Center"), command=lambda a=axis: self._center_stick(a))  # type: ignore[misc]
            center.grid(row=row, column=2, padx=4)
        buttons = ttk.Frame(sticks)
        buttons.grid(row=4, column=0, columnspan=3, sticky="w", pady=4)
        center_all = ttk.Button(buttons, text=_("Center all"), command=self._center_all_sticks)
        center_all.pack(side="left", padx=4)
        show_tooltip(center_all, _("Return every simulated stick to neutral immediately."))
        release = ttk.Button(buttons, text=_("Release to transmitter"), command=self._release_sticks)
        release.pack(side="left", padx=4)
        show_tooltip(release, _("Stop simulating sticks and give control back to the RC transmitter."))

    def _create_tilt_rotor_tab(self) -> None:
        tab = self._new_tab(_("4. Tilt rotors"))
        problem = self.model.tilt_setup_problem()
        if problem:
            self._no_channels(tab, problem)
            return
        settings = ttk.LabelFrame(tab, text=_("Tilt settings (verify or change)"))
        settings.pack(fill="x", pady=4)
        tooltips = {
            "Q_TILT_TYPE": _("0 Continuous, 1 Binary, 2 Vectored yaw, 3 Bicopter"),
            "Q_TILT_YAW_ANGLE": _("Vectored yaw: degrees the tilt mechanism can travel past vertical"),
            "Q_TILT_FIX_ANGLE": _("Maximum tilt angle used for fixed-wing roll and pitch assistance"),
        }
        for row, name in enumerate(TILT_SETTING_PARAMETERS):
            ttk.Label(settings, text=name).grid(row=row, column=0, sticky="w", padx=4)
            spinbox = _LiveSpinbox(
                settings,
                self.model.tilt_setting_value(name) or 0,
                lambda value, n=name: self._on_tilt_setting(n, value),  # type: ignore[misc]
                from_=0,
                to=90,
                increment=1,
            )
            spinbox.grid(row=row, column=1, padx=4)
            self._endpoint_spinboxes[name] = spinbox
            show_tooltip(spinbox, tooltips[name])
        if self.model.tilt_type() in self.model.tilt_type_options():
            ttk.Label(settings, text=self.model.tilt_type_options()[self.model.tilt_type()]).grid(row=0, column=2, sticky="w")
        ttk.Button(
            settings,
            text=_("Acknowledge settings"),
            command=lambda: self._save(list(TILT_SETTING_PARAMETERS), _("Tilt-rotor settings verified")),
        ).grid(row=len(TILT_SETTING_PARAMETERS), column=0, columnspan=2, sticky="w", pady=4)

        channels = self.model.tilt_servo_channels()
        forward = ttk.LabelFrame(tab, text=_("Forward flight (MANUAL)"))
        forward.pack(fill="x", pady=4)
        self._mode_button(forward, PlaneMode.MANUAL).grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(
            forward,
            text=_(
                "Tick Reversed until every motor points forward, then adjust the highlighted end point "
                "until each motor is exactly horizontal."
            ),
            wraplength=WRAP_LENGTH,
            justify="left",
        ).grid(row=1, column=0, columnspan=4, sticky="w")
        for row, channel in enumerate(channels, start=2):
            ttk.Label(forward, text=channel.display_name).grid(row=row, column=0, sticky="w", padx=4)
            self._pwm_label(forward, channel).grid(row=row, column=1, padx=4)
            var = tk.BooleanVar(value=self.model.is_servo_reversed(channel))
            self._servo_reversed_vars[channel.number] = var
            ttk.Checkbutton(
                forward,
                text=_("Reversed"),
                variable=var,
                command=lambda ch=channel, v=var: self._on_tilt_reversed(ch, reversed_=v.get()),  # type: ignore[misc]
            ).grid(row=row, column=2, sticky="w")
            self._tilt_endpoint_cell(forward, channel, row, hover=False)

        hover = ttk.LabelFrame(tab, text=_("Hover (QSTABILIZE)"))
        hover.pack(fill="x", pady=4)
        self._mode_button(hover, PlaneMode.QSTABILIZE).grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(
            hover,
            text=_("Adjust the highlighted end point until each motor points exactly vertical."),
            wraplength=WRAP_LENGTH,
            justify="left",
        ).grid(row=1, column=0, columnspan=4, sticky="w")
        for row, channel in enumerate(channels, start=2):
            ttk.Label(hover, text=channel.display_name).grid(row=row, column=0, sticky="w", padx=4)
            self._pwm_label(hover, channel).grid(row=row, column=1, padx=4)
            self._tilt_endpoint_cell(hover, channel, row, hover=True)

        self._save_button(
            tab,
            lambda: [
                *(channel.param("REVERSED") for channel in self.model.tilt_servo_channels()),
                *self.model.endpoint_parameters(self.model.tilt_servo_channels(), (EndpointKind.MIN, EndpointKind.MAX)),
            ],
            _("Tilt servo end points adjusted for forward flight and hover"),
        )

    def _tilt_endpoint_cell(self, parent: tk.Misc, channel: ServoChannel, row: int, *, hover: bool) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=3, sticky="w")
        label_var = tk.StringVar()
        ttk.Label(frame, textvariable=label_var, width=5).pack(side="left")
        cell_key = f"tilt_{'hover' if hover else 'forward'}_{channel.number}"

        def kind() -> EndpointKind:
            forward_kind, hover_kind = self.model.tilt_endpoints(channel)
            return hover_kind if hover else forward_kind

        def on_change(value: float) -> None:
            self._on_endpoint(channel, kind(), value)

        spinbox = _LiveSpinbox(frame, self.model.servo_endpoint(channel, kind()), on_change, from_=500, to=2200, increment=5)
        spinbox.pack(side="left")
        show_tooltip(spinbox, _("Live-write the SERVOx_MIN or SERVOx_MAX end point shown on the left."))
        self._endpoint_spinboxes[cell_key] = spinbox

        def refresh() -> None:
            label_var.set(kind().value)
            spinbox.set_value(self.model.servo_endpoint(channel, kind()))

        refresh()
        setattr(spinbox, "refresh_endpoint", refresh)  # noqa: B010

    def _endpoint_spinbox(self, parent: tk.Misc, channel: ServoChannel, kind: EndpointKind) -> _LiveSpinbox:
        spinbox = _LiveSpinbox(
            parent,
            self.model.servo_endpoint(channel, kind),
            lambda value: self._on_endpoint(channel, kind, value),
            from_=500,
            to=2200,
            increment=SPINBOX_INCREMENT_PWM,
        )
        show_tooltip(spinbox, _("Live-write %(param)s") % {"param": channel.param(kind.value)})
        self._endpoint_spinboxes[channel.param(kind.value)] = spinbox
        return spinbox

    # ------------------------------------------------------------------ actions

    def _live(self, action: Callable[[], None]) -> bool:
        try:
            action()
        except ControlSurfaceSetupError as error:
            showerror(_("Control surface setup"), str(error))
            self._sync_controls()
            return False
        return True

    def _switch_mode(self, mode: PlaneMode) -> None:
        ok, message = self.model.battery_voltage_status()
        if not ok:
            showerror(_("Servo power"), message + "\n" + _("The servos need battery power for this check."))
            return
        if mode != PlaneMode.MANUAL:
            self._release_sticks()
        if self._live(lambda: self.model.set_flight_mode(mode)):
            self._update_mode()

    def _on_endpoint(self, channel: ServoChannel, kind: EndpointKind, value: float) -> None:
        if not float(value).is_integer():
            showerror(_("Invalid value"), _("Please enter a whole number of microseconds."))
            self._sync_controls()
            return
        if self._live(lambda: self.model.set_servo_endpoint(channel, kind, int(value))):
            self._update_trim_warning(channel)

    def _on_tilt_setting(self, name: str, value: float) -> None:
        self._live(lambda: self.model.set_tilt_setting(name, value))
        self._refresh_tilt_endpoints()

    def _on_tilt_reversed(self, channel: ServoChannel, *, reversed_: bool) -> None:
        self._live(lambda: self.model.set_servo_reversed(channel, reversed_=reversed_))
        self._refresh_tilt_endpoints()

    def _refresh_tilt_endpoints(self) -> None:
        for key, spinbox in self._endpoint_spinboxes.items():
            if key.startswith("tilt_"):
                refresh = getattr(spinbox, "refresh_endpoint", None)
                if callable(refresh):
                    refresh()

    def _update_trim_warning(self, channel: ServoChannel) -> None:
        label = self._trim_warnings.get(channel.number)
        if label is None:
            return
        trim = self.model.servo_endpoint(channel, EndpointKind.TRIM)
        if self.model.trim_needs_mechanical_adjustment(trim):
            label.configure(text=_("Trim is more than 50 µs from 1500; adjust the linkage mechanically."))
        else:
            label.configure(text="")

    def _on_stick(self, axis: StickAxis, percent: float) -> None:
        self.model.set_stick_fraction(axis, percent / 100.0)
        if percent != 0 or self.model.override_active:
            self._send_override()

    def _center_stick(self, axis: StickAxis) -> None:
        self._stick_scales[axis].set(0)
        self.model.set_stick_fraction(axis, 0.0)
        if self.model.override_active:
            self._send_override()

    def _center_all_sticks(self) -> None:
        for scale in self._stick_scales.values():
            scale.set(0)
        with suppress(ControlSurfaceSetupError):
            self.model.center_sticks()

    def _release_sticks(self) -> None:
        cancel_plugin_timer(self, self._override_timer)
        self._override_timer = None
        for scale in self._stick_scales.values():
            scale.set(0)
        self.model.release_stick_override()

    def _send_override(self) -> None:
        cancel_plugin_timer(self, self._override_timer)
        self._override_timer = None
        try:
            self.model.send_stick_override()
        except ControlSurfaceSetupError as error:
            logging_warning(_("Could not send simulated stick input: %(error)s"), {"error": error})
            return
        if self._active:
            self._override_timer = self.after(OVERRIDE_PERIOD_MS, self._send_override)

    def _save(self, names: list[str], reason: str) -> None:
        result: SaveResult = self.model.save_parameters(names, reason)
        if result.success:
            showinfo(_("Control surface setup"), result.message())
        else:
            showwarning(_("Control surface setup"), result.message())
        reboot = self.model.pending_reboot_parameters()
        if reboot:
            showwarning(
                _("Reboot required"),
                _("Reboot the flight controller for these changes to take effect: %(names)s") % {"names": ", ".join(reboot)},
            )
        refresh_parameter_editor_table(self.base_window)

    # ------------------------------------------------------------------ periodic updates

    def _sync_controls(self) -> None:
        """Reload every control from the model after a failed write."""
        for channel in [*self.model.control_surface_channels(), *self.model.tilt_servo_channels()]:
            var = self._servo_reversed_vars.get(channel.number)
            if var is not None:
                var.set(self.model.is_servo_reversed(channel))
            for kind in EndpointKind:
                spinbox = self._endpoint_spinboxes.get(channel.param(kind.value))
                if spinbox is not None:
                    spinbox.set_value(self.model.servo_endpoint(channel, kind))
        for axis, var in self._rc_reversed_vars.items():
            var.set(self.model.is_rc_reversed(axis))
        for name in TILT_SETTING_PARAMETERS:
            spinbox = self._endpoint_spinboxes.get(name)
            value = self.model.tilt_setting_value(name)
            if spinbox is not None and value is not None:
                spinbox.set_value(value)
        self._refresh_tilt_endpoints()

    def _update_mode(self) -> None:
        self._mode_var.set(_("Flight mode: %(mode)s") % {"mode": self.model.current_mode_name()})

    def _on_telemetry_timer(self) -> None:
        self._telemetry_timer = None
        if not self._active:
            return
        try:
            self.model.poll_telemetry()
        except Exception as error:  # pylint: disable=broad-exception-caught
            logging_warning(_("Servo telemetry error: %(error)s"), {"error": error})
        for channel, label in self._pwm_labels:
            pwm = self.model.servo_pwm(channel.number)
            label.configure(text=f"{pwm} µs" if pwm is not None else "---- µs")
        self._update_mode()
        self._telemetry_timer = self.after(TELEMETRY_PERIOD_MS, self._on_telemetry_timer)

    def _on_battery_timer(self) -> None:
        self._battery_timer = None
        if not self._active:
            return
        self._battery_ok, message = self.model.battery_voltage_status()
        self._battery_var.set(message)
        self._battery_label.configure(foreground="green" if self._battery_ok else "red")
        self._battery_timer = self.after(BATTERY_PERIOD_MS, self._on_battery_timer)

    def _stop_timers(self) -> None:
        for name in ("_telemetry_timer", "_override_timer", "_battery_timer"):
            cancel_plugin_timer(self, getattr(self, name))
            setattr(self, name, None)

    # ------------------------------------------------------------------ lifecycle

    def on_activate(self) -> None:
        """Start telemetry polling and the battery check."""
        if self._active:
            return
        self._active = True
        self._sync_controls()
        self._on_telemetry_timer()
        self._on_battery_timer()

    def on_deactivate(self) -> None:
        """Stop polling, release simulated sticks and restore the original flight mode."""
        self._active = False
        self._stop_timers()
        for scale in self._stick_scales.values():
            scale.set(0)
        try:
            self.model.shutdown()
        except Exception as error:  # pylint: disable=broad-exception-caught
            logging_warning(_("Control surface setup cleanup failed: %(error)s"), {"error": error})

    def on_suspend(self, reason: PluginPauseReason = PluginPauseReason.EXCLUSIVE_OPERATION) -> None:
        """Yield the link; release simulated sticks for tools, send nothing during recovery."""
        self._active = False
        self._stop_timers()
        if reason is PluginPauseReason.EXCLUSIVE_OPERATION:
            for scale in self._stick_scales.values():
                scale.set(0)
            self.model.release_stick_override()

    def on_resume(self) -> None:
        """Resume telemetry polling without re-sending stick input."""
        self.on_activate()

    def destroy(self) -> None:
        """Clean up timers, overrides and flight-mode changes before destruction."""
        if self._active:
            self.on_deactivate()
        self._stop_timers()
        super().destroy()


def _create_control_surface_setup_view(
    parent: tk.Frame | ttk.Frame, model: object, base_window: object
) -> ControlSurfaceSetupView:
    """Create the control surface setup view for the plugin factory."""
    return ControlSurfaceSetupView(parent, model, base_window)  # type: ignore[arg-type]


def _create_control_surface_setup_model(context: PluginModelContext) -> ControlSurfaceSetupDataModel:
    """Create the control surface setup data model from application dependencies."""
    return ControlSurfaceSetupDataModel(context.flight_controller, context.local_filesystem, context.parameter_editor)


def register_control_surface_setup_plugin() -> None:
    """Register the control surface setup plugin with the factory."""
    plugin_factory.register(
        PLUGIN_CONTROL_SURFACE_SETUP,
        _create_control_surface_setup_view,
        _create_control_surface_setup_model,
        requires_flight_controller=True,
    )
