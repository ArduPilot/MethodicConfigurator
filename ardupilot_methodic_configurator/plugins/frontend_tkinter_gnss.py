"""
Live GNSS receiver status embedded in the parameter editor.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_font import create_scaled_font, get_safe_font_config
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip
from ardupilot_methodic_configurator.plugins.backend_gnss import GnssBackend
from ardupilot_methodic_configurator.plugins.data_model_gnss import GnssDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_helpers import cancel_plugin_timer
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_GNSS
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory
from ardupilot_methodic_configurator.plugins.plugin_protocol import PluginPauseReason


class GnssView(ttk.Frame):  # pylint: disable=too-many-ancestors
    """Show each receiver's latest fix with units and explicit unavailable readings."""

    def __init__(self, parent: tk.Frame | ttk.Frame, model: GnssDataModel, base_window: BaseWindow) -> None:
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        self.backend = GnssBackend(model.flight_controller)
        self._timer_id: str | None = None
        self._display_font = create_scaled_font(get_safe_font_config(), scale_factor=0.8)
        scroll = ScrollFrame(self)
        scroll.pack(fill="both", expand=True, padx=4, pady=4)
        content = scroll.view_port
        labels = (
            _("Status"),
            _("Latitude, longitude (°)"),
            _("Height above mean sea level (m)"),
            _("Local time (FC)"),
            _("Number of satellites"),
            _("Horizontal, vertical accuracy (m)"),
        )
        self.values = [[tk.StringVar(self, value=_("N/A")) for _label in labels] for _receiver in range(2)]
        self._second_receiver_widgets: list[ttk.Label] = []
        for column, title in enumerate((_("GNSS"), _("Receiver 1"), _("Receiver 2"))):
            header = ttk.Label(content, text=title, font=self._display_font)
            header.grid(row=0, column=column, sticky="w", padx=8, pady=4)
            if column == 2:
                self._second_receiver_widgets.append(header)
        for row, label in enumerate(labels, start=1):
            field_label = ttk.Label(content, text=label, font=self._display_font)
            field_label.grid(row=row, column=0, sticky="w", padx=8, pady=2)
            if row == 4:
                show_tooltip(
                    field_label,
                    _(
                        "Flight controller UTC, normally synchronized from GNSS, plus BRD_RTC_TZ_MIN in minutes. "
                        "N/A means UTC or the configured timezone offset is unavailable."
                    ),
                )
            for receiver in range(2):
                value = ttk.Label(content, textvariable=self.values[receiver][row - 1], font=self._display_font)
                value.grid(row=row, column=receiver + 1, sticky="w", padx=8, pady=2)
                if receiver == 1:
                    self._second_receiver_widgets.append(value)
                show_tooltip(value, _("Live receiver data. N/A means unavailable; readings expire when telemetry stops."))
        self._set_second_receiver_visible(visible=False)
        self.on_activate()

    def _set_second_receiver_visible(self, *, visible: bool) -> None:
        """Reserve a second column only while telemetry reports a detected receiver."""
        for widget in self._second_receiver_widgets:
            if visible:
                widget.grid()
            else:
                widget.grid_remove()

    def _poll(self) -> None:
        self._timer_id = None
        if not self.tk.call("grab", "current", str(self)) and not self.base_window.navigation_lock.locked:
            receiver_readings = self.model.update(self.backend.poll())
            self._set_second_receiver_visible(visible=self.model.second_receiver_present)
            for variables, readings in zip(self.values, receiver_readings, strict=True):
                display_readings = (
                    readings[0],
                    f"{readings[1]}, {readings[2]}",
                    readings[3],
                    readings[4],
                    readings[5],
                    f"{readings[6]}, {readings[7]}",
                )
                for variable, reading in zip(variables, display_readings, strict=True):
                    variable.set(reading)
        self.on_activate()

    def on_activate(self) -> None:
        """Schedule exactly one bounded telemetry poll."""
        if self._timer_id is None:
            self._timer_id = self.after(250, self._poll)

    def on_deactivate(self) -> None:
        """Cancel polling and detach the observation hook before yielding the connection."""
        cancel_plugin_timer(self, self._timer_id)
        self._timer_id = None
        self.backend.close()
        self._set_second_receiver_visible(visible=False)
        for variables in self.values:
            for variable in variables:
                variable.set(_("N/A"))

    # pylint: disable-next=unused-argument
    def on_suspend(self, reason: PluginPauseReason = PluginPauseReason.EXCLUSIVE_OPERATION) -> None:  # noqa: ARG002
        """Yield the receive loop during exclusive operations and connection recovery."""
        self.on_deactivate()

    def on_resume(self) -> None:
        """Resume polling with fresh receiver snapshots."""
        self.on_activate()

    def destroy(self) -> None:
        self.on_deactivate()
        super().destroy()


def _create_view(parent: tk.Frame | ttk.Frame, model: object, base_window: object) -> GnssView:
    return GnssView(parent, model, base_window)  # type: ignore[arg-type]


def _create_model(context: PluginModelContext) -> GnssDataModel:
    return GnssDataModel(context.flight_controller)


def register_gnss_plugin() -> None:
    """Register GNSS monitoring for a connected flight controller."""
    plugin_factory.register(PLUGIN_GNSS, _create_view, _create_model)
