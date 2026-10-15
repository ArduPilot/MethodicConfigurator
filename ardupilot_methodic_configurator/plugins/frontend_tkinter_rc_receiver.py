"""
Compact receiver connection and failsafe monitor for the parameter editor.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from contextlib import suppress
from tkinter import ttk

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.frontend_tkinter_show import Tooltip
from ardupilot_methodic_configurator.plugins.data_model_rc_receiver import RCReceiverDataModel, RCReceiverState
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_RC_RECEIVER
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory

_PWM_MIN = 800
_PWM_MAX = 2200
_POLL_MS = 100


class RCReceiverView(ttk.Frame):  # pylint: disable=too-many-ancestors,too-many-instance-attributes
    """Present five raw input channels, receiver RSSI and explicit RC failsafe status."""

    def __init__(self, parent: tk.Frame | ttk.Frame, model: RCReceiverDataModel, base_window: BaseWindow) -> None:
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        self._timer_id: str | None = None
        self._setup_ui()
        self._show_state(RCReceiverState())
        self.on_activate()

    def _setup_ui(self) -> None:
        scroll = ScrollFrame(self)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)
        content = scroll.view_port
        content.columnconfigure(1, weight=1, uniform="receiver_width")
        content.columnconfigure(3, weight=3, uniform="receiver_width")
        self.instructions = ttk.Label(
            content,
            text=_(
                "Move the sticks and switches on the RC controller to test that at least the first five channels are working. "
                "Power off the RC transmitter (controller) and check that RC failsafe is detected, "
                "then power it back on to check recovery. "
                "If necessary change the parameters on the right and press 'Upload selected params to FC' to activate them."
            ),
            wraplength=400,
            justify="left",
        )
        self.instructions.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        content.bind("<Configure>", self._resize_instructions, add="+")
        self.channel_bars: list[ttk.Progressbar] = []
        self.channel_values: list[ttk.Label] = []
        for channel in range(1, 6):
            ttk.Label(content, text=_("CH%(channel)d") % {"channel": channel}).grid(
                row=channel, column=0, sticky="w", padx=(0, 6), pady=3
            )
            channel_bar = ttk.Progressbar(content, maximum=_PWM_MAX - _PWM_MIN, length=25)
            channel_bar.grid(row=channel, column=1, sticky="ew", pady=3)
            Tooltip(channel_bar, _("Live RC input in microseconds (800-2200 µs). Move this channel to check reception."))
            value = ttk.Label(content, width=12, anchor="e")
            value.grid(row=channel, column=2, sticky="e", padx=(6, 4))
            self.channel_bars.append(channel_bar)
            self.channel_values.append(value)

        ttk.Label(content, text=_("RSSI")).grid(row=6, column=0, sticky="w", pady=3)
        self.rssi_bar = ttk.Progressbar(content, maximum=254, length=25)
        self.rssi_bar.grid(row=6, column=1, sticky="ew", pady=3)
        Tooltip(self.rssi_bar, _("Receiver signal strength as reported by the FC (0-254, device-dependent scale)."))
        self.rssi_value = ttk.Label(content, width=12, anchor="e")
        self.rssi_value.grid(row=6, column=2, sticky="e", padx=(6, 4))
        status_frame = ttk.Frame(content)
        status_frame.grid(row=1, column=3, rowspan=6, sticky="nsew", padx=(12, 4))
        self.input_status = ttk.Label(status_frame, width=1, wraplength=300, justify="left")
        self.receiver_status = ttk.Label(status_frame, width=1, wraplength=300, justify="left")
        self.failsafe_status = ttk.Label(status_frame, width=1, wraplength=300, justify="left")
        self.failsafe_history = ttk.Label(status_frame, width=1, wraplength=300, justify="left")
        for label in (self.input_status, self.receiver_status, self.failsafe_status, self.failsafe_history):
            label.pack(fill="x", anchor="w", pady=3)
        status_frame.bind("<Configure>", self._resize_status_text, add="+")

    def _resize_instructions(self, event: tk.Event) -> None:
        self.instructions.configure(wraplength=max(100, event.width - 12))

    def _resize_status_text(self, event: tk.Event) -> None:
        for label in (self.input_status, self.receiver_status, self.failsafe_status, self.failsafe_history):
            label.configure(wraplength=max(1, event.width))

    def _show_state(self, state: RCReceiverState) -> None:
        for channel_bar, label, pwm in zip(self.channel_bars, self.channel_values, state.channels, strict=True):
            channel_bar.configure(value=0 if pwm is None else max(0, min(pwm, _PWM_MAX) - _PWM_MIN))
            label.configure(text=_("Unavailable") if pwm is None else _("%(pwm)d µs") % {"pwm": pwm})
        self.rssi_bar.configure(value=state.rssi if state.rssi is not None else 0)
        self.rssi_value.configure(text=_("Unavailable") if state.rssi is None else f"{state.rssi} / 254")
        if not state.connected:
            input_text = _("Flight controller disconnected.")
            input_color = "orange"
        elif state.receiving_channels:
            input_text = _("RC channel data received from the flight controller.")
            input_color = "green"
        else:
            input_text = _("No current RC channel data. Check receiver wiring, power and transmitter binding.")
            input_color = "red"
        self.input_status.configure(text=input_text, foreground=input_color)
        if state.receiver_present is None:
            receiver_text = _("Receiver status: unknown.")
            receiver_color = "red"
        elif state.receiver_present:
            receiver_text = _("Receiver: RC input has been detected by the flight controller.")
            receiver_color = "green"
        else:
            receiver_text = _("Receiver: no RC input detected by the flight controller yet.")
            receiver_color = "orange"
        self.receiver_status.configure(text=receiver_text, foreground=receiver_color)
        if state.failsafe is None:
            failsafe_text, color = _("RC failsafe: unknown (status unavailable)."), "red"
        elif state.failsafe:
            failsafe_text, color = _("RC failsafe: DETECTED."), "black"
        else:
            failsafe_text, color = _("RC failsafe: not active."), "black"
        self.failsafe_status.configure(text=failsafe_text, foreground=color)
        self.failsafe_history.configure(
            text=_("RC failsafe detected during this test.")
            if state.failsafe_detected
            else _("RC failsafe has not been detected during this test."),
            foreground="green" if state.failsafe_detected else "red",
        )

    def _check_telemetry(self) -> None:
        self._timer_id = None
        self._show_state(self.model.get_receiver_state())
        self._timer_id = self.after(_POLL_MS, self._check_telemetry)

    def on_activate(self) -> None:
        """Resume exactly one polling loop."""
        if self._timer_id is None:
            self._timer_id = self.after(_POLL_MS, self._check_telemetry)

    def on_deactivate(self) -> None:
        """Yield the shared receiver while hidden or while diagnostics owns it."""
        if self._timer_id is not None:
            with suppress(tk.TclError):
                self.after_cancel(self._timer_id)
            self._timer_id = None
        self.model.stop_monitoring()

    def destroy(self) -> None:
        self.on_deactivate()
        super().destroy()


def _create_rc_receiver_view(parent: tk.Frame | ttk.Frame, model: object, base_window: object) -> RCReceiverView:
    return RCReceiverView(parent, model, base_window)  # type: ignore[arg-type]


def _create_rc_receiver_model(context: PluginModelContext) -> RCReceiverDataModel:
    return RCReceiverDataModel(context.flight_controller)


def register_rc_receiver_plugin() -> None:
    """Register both factories using the existing FC-required plugin dispatch."""
    plugin_factory.register(PLUGIN_RC_RECEIVER, _create_rc_receiver_view, _create_rc_receiver_model)
