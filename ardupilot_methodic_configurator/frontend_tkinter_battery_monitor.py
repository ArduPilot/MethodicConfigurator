"""
GUI for battery monitor plugin.

This file implements the Tkinter frontend for the battery monitor plugin following
the Model-View separation pattern.

The BatteryMonitorView class provides:
- Real-time battery voltage and current display
- Color-coded voltage status indication
- Simple, focused interface showing only battery metrics

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from logging import debug as logging_debug
from tkinter import Frame, ttk
from typing import Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_battery_monitor import BatteryMonitorDataModel
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.plugin_constants import PLUGIN_BATTERY_MONITOR
from ardupilot_methodic_configurator.plugin_factory import plugin_factory


class BatteryMonitorView(Frame):
    """GUI for battery monitor plugin."""

    def __init__(
        self,
        parent: Union[tk.Frame, ttk.Frame],
        model: BatteryMonitorDataModel,
        base_window: BaseWindow,
    ) -> None:
        """
        Initialize the battery monitor view.

        Args:
            parent: Parent widget
            model: Data model for battery monitoring
            base_window: Parent BaseWindow instance

        """
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        self.root_window = base_window.root if hasattr(base_window, "root") else base_window

        # Create UI components
        self._setup_ui()

        # Start periodic updates
        self._update_battery_status()
        self._schedule_next_update()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        title_label = ttk.Label(
            main_frame,
            text=_("Battery Monitor"),
            font=("TkDefaultFont", 14, "bold"),
        )
        title_label.pack(pady=(0, 20))

        # Info text
        info_text = _(
            "This monitor displays real-time battery voltage and current readings.\n"
            "The voltage display is color-coded:\n"
            "  • Green: Safe voltage range\n"
            "  • Red: Critical voltage (outside safe range)\n"
            "  • Gray: Battery monitoring disabled or unavailable"
        )
        info_label = ttk.Label(main_frame, text=info_text, justify="left")
        info_label.pack(pady=(0, 30))

        # Battery status display frame
        status_frame = ttk.LabelFrame(main_frame, text=_("Battery Status"), padding=20)
        status_frame.pack(fill="both", expand=True)

        # Voltage display
        voltage_container = ttk.Frame(status_frame)
        voltage_container.pack(pady=10)
        ttk.Label(voltage_container, text=_("Voltage:"), font=("TkDefaultFont", 12)).pack(side="left", padx=5)
        self.voltage_value_label = ttk.Label(
            voltage_container,
            text=_("N/A"),
            font=("TkDefaultFont", 16, "bold"),
        )
        self.voltage_value_label.pack(side="left", padx=5)

        # Current display
        current_container = ttk.Frame(status_frame)
        current_container.pack(pady=10)
        ttk.Label(current_container, text=_("Current:"), font=("TkDefaultFont", 12)).pack(side="left", padx=5)
        self.current_value_label = ttk.Label(
            current_container,
            text=_("N/A"),
            font=("TkDefaultFont", 16, "bold"),
        )
        self.current_value_label.pack(side="left", padx=5)

    def _update_battery_status(self) -> None:
        """Update battery voltage and current labels."""
        voltage_text, current_text = self._get_battery_display_text()

        self.voltage_value_label.config(text=voltage_text)
        self.current_value_label.config(text=current_text)

        # Update color based on voltage status
        color = self.model.get_battery_status_color()
        self.voltage_value_label.config(foreground=color)

        logging_debug(
            _("Battery status updated: %(voltage)s, %(current)s"), {"voltage": voltage_text, "current": current_text}
        )

    def _get_battery_display_text(self) -> tuple[str, str]:
        """
        Get formatted battery status text for display.

        Returns:
            tuple[str, str]: (voltage_text, current_text)

        """
        if not self.model.is_battery_monitoring_enabled():
            return _("Disabled"), _("Disabled")

        status = self.model.get_battery_status()
        if status:
            voltage, current = status
            voltage_text = _("%(volt).2f V") % {"volt": voltage}
            current_text = _("%(curr).2f A") % {"curr": current}
            return voltage_text, current_text
        return _("N/A"), _("N/A")

    def _schedule_next_update(self) -> None:
        """Schedule the next battery status update."""
        # Update every 500ms (0.5 seconds)
        self.after(500, self._periodic_update)

    def _periodic_update(self) -> None:
        """Periodic update callback."""
        if self.model.refresh_connection_status():
            self._update_battery_status()
        self._schedule_next_update()

    def on_activate(self) -> None:
        """
        Called when the plugin becomes active (visible).

        Refreshes battery status to ensure the display is up-to-date.
        """
        if self.model.refresh_connection_status():
            self._update_battery_status()
        logging_debug(_("Battery monitor plugin activated"))

    def on_deactivate(self) -> None:
        """
        Called when the plugin becomes inactive (hidden).

        Currently no special cleanup needed for battery monitor.
        """
        logging_debug(_("Battery monitor plugin deactivated"))


def _create_battery_monitor_view(
    parent: Union[tk.Frame, ttk.Frame],
    model: object,
    base_window: object,
) -> "BatteryMonitorView":
    """
    Factory function to create BatteryMonitorView instances.

    This function trusts that the caller provides the correct types
    as per the plugin protocol (duck typing approach).

    Args:
        parent: The parent frame
        model: The BatteryMonitorDataModel instance (passed as object for protocol compliance)
        base_window: The BaseWindow instance (passed as object for protocol compliance)

    Returns:
        A new BatteryMonitorView instance

    """
    # Trust the caller to provide correct types (protocol-based duck typing)
    # Type checker will verify this at static analysis time
    return BatteryMonitorView(parent, model, base_window)  # type: ignore[arg-type]


def register_battery_monitor_plugin() -> None:
    """Register the battery monitor plugin with the factory."""
    plugin_factory.register(PLUGIN_BATTERY_MONITOR, _create_battery_monitor_view)
