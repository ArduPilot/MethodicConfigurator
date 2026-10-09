"""
GUI for battery monitor plugin.

This file implements the Tkinter frontend for the battery monitor plugin following
the Model-View separation pattern.

The BatteryMonitorView class provides:
- Real-time battery voltage and current display
- Color-coded voltage status indication
- Simple, focused interface showing only battery metrics

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import ArgumentParser, Namespace
from logging import debug as logging_debug
from logging import error as logging_error
from logging import warning as logging_warning
from math import isnan
from tkinter import Frame, ttk
from tkinter.messagebox import showerror

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.__main__ import (
    ApplicationState,
    initialize_flight_controller,
    setup_logging,
)
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_scroll_frame import ScrollFrame
from ardupilot_methodic_configurator.plugins.data_model_battery_monitor import (
    BATTERY_UPDATE_INTERVAL_MS,
    BatteryMonitorDataModel,
)
from ardupilot_methodic_configurator.plugins.plugin_constants import PLUGIN_BATTERY_MONITOR
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginModelContext, plugin_factory


class BatteryMonitorView(Frame):
    """GUI for battery monitor plugin."""

    def __init__(
        self,
        parent: tk.Frame | ttk.Frame,
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
        self._timer_id: str | None = None
        self._battery_rows: dict[int, tuple[ttk.Label, ttk.Label, ttk.Label]] = {}

        # Create UI components (labels initialized in _setup_ui)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Main container
        self.scroll_frame = ScrollFrame(self)
        self.scroll_frame.pack(fill="both", expand=True)
        main_frame = self.scroll_frame.view_port

        # Info text
        info_text = _(
            "Change the parameters to the right and press\n"
            '"Upload selected params to FC" to see their results.\n'
            "  • Green: Above this battery's arming voltage\n"
            "    (Battery 1 must also be below the motor voltage limit)\n"
            "  • Red: Critical voltage (outside safe range)\n"
            "  • Gray: Battery monitoring disabled or unavailable\n"
        )
        info_label = ttk.Label(main_frame, text=info_text, justify="left")
        info_label.pack(pady=(0, 10))

        # Display each battery as its own row, with its number at the left.
        self.battery_display_container = ttk.Frame(main_frame)
        self.battery_display_container.pack(pady=10)
        for column, heading in enumerate((_("Battery"), _("Voltage"), _("Current"))):
            ttk.Label(self.battery_display_container, text=f"{heading}", font=("TkDefaultFont", 12, "bold")).grid(
                row=0, column=column, sticky="w", padx=12, pady=(0, 6)
            )

        self._display_battery_rows(
            {battery_id: (_("N/A"), _("N/A"), "gray") for battery_id in self.model.get_enabled_battery_ids() or [0]}
        )

    def _update_battery_status(self) -> None:
        """Update one display row for each configured battery monitor."""
        self._display_battery_rows(self._get_battery_display_rows())

    def _display_battery_rows(self, display_rows: dict[int, tuple[str, str, str]]) -> None:
        """Create, update and remove battery labels to reflect the current configuration."""
        active_batteries = set(display_rows)

        for battery_id in set(self._battery_rows) - active_batteries:
            for label in self._battery_rows.pop(battery_id):
                label.destroy()

        for row, (battery_id, (voltage_text, current_text, color)) in enumerate(sorted(display_rows.items()), start=1):
            labels = self._battery_rows.get(battery_id)
            if labels is None:
                labels = (
                    ttk.Label(self.battery_display_container, font=("TkDefaultFont", 12, "bold")),
                    ttk.Label(self.battery_display_container, font=("TkDefaultFont", 16, "bold")),
                    ttk.Label(self.battery_display_container, font=("TkDefaultFont", 16, "bold")),
                )
                self._battery_rows[battery_id] = labels
            battery_label, voltage_label, current_label = labels
            battery_label.config(text=_("Battery %(number)d:") % {"number": battery_id + 1})
            voltage_label.config(text=voltage_text, foreground=color)
            current_label.config(text=current_text)
            for column, label in enumerate(labels):
                label.grid(row=row, column=column, sticky="w", padx=12, pady=4)

            logging_debug(
                _("Battery %(number)d status updated: %(voltage)s, %(current)s"),
                {"number": battery_id + 1, "voltage": voltage_text, "current": current_text},
            )

    def _get_battery_display_rows(self) -> dict[int, tuple[str, str, str]]:
        """Return display text and voltage color for each zero-based battery ID."""
        battery_ids = self.model.get_enabled_battery_ids()
        statuses = self.model.get_battery_statuses() or {}
        if not battery_ids:
            return {0: (_("Disabled"), _("Disabled"), "gray")}
        rows = {}
        for battery_id in battery_ids:
            status = statuses.get(battery_id)
            if status is None:
                rows[battery_id] = (_("N/A"), _("N/A"), "gray")
                continue
            voltage, current = status
            rows[battery_id] = (
                _("N/A") if isnan(voltage) else f"{voltage:.2f} V",
                _("N/A") if isnan(current) else f"{current:.2f} A",
                self.model.get_battery_status_color(battery_id, voltage),
            )
        return rows

    def _schedule_next_update(self) -> None:
        """Schedule the next battery status update."""
        self._timer_id = self.after(BATTERY_UPDATE_INTERVAL_MS, self._periodic_update)

    def _periodic_update(self) -> None:
        """Periodic update callback."""
        self._update_battery_status()
        self._schedule_next_update()

    def on_activate(self) -> None:
        """
        Called when the plugin becomes active (visible).

        Starts periodic updates and refreshes battery status to ensure the display is up-to-date.
        """
        self._update_battery_status()
        # Start periodic updates if not already running
        if self._timer_id is None:
            self._schedule_next_update()
        logging_debug(_("Battery monitor plugin activated"))

    def on_deactivate(self) -> None:
        """
        Called when the plugin becomes inactive (hidden).

        Cancels the periodic update timer and stops data model monitoring to prevent resource leaks.
        """
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None
        self.model.stop_monitoring()
        logging_debug(_("Battery monitor plugin deactivated"))

    def destroy(self) -> None:
        """
        Clean up the plugin and release all resources.

        Ensures any active timers are cancelled and model monitoring is stopped before the widget is destroyed.
        """
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None
        self.model.stop_monitoring()
        super().destroy()


def _create_battery_monitor_view(
    parent: tk.Frame | ttk.Frame,
    model: object,
    base_window: object,
) -> "BatteryMonitorView":
    """
    Factory function to create BatteryMonitorView instances.

    This function signature follows the plugin protocol which uses object types.
    The caller ensures correct types are passed (BatteryMonitorDataModel and BaseWindow).

    Args:
        parent: The parent frame
        model: The BatteryMonitorDataModel instance
        base_window: The BaseWindow instance

    Returns:
        A new BatteryMonitorView instance

    """
    # Type checker verifies correct types are provided by the caller
    return BatteryMonitorView(parent, model, base_window)  # type: ignore[arg-type]


def _create_battery_monitor_model(context: PluginModelContext) -> BatteryMonitorDataModel:
    """Create the plugin data model from registered application dependencies."""
    return BatteryMonitorDataModel(context.flight_controller)


def register_battery_monitor_plugin() -> None:
    """Register the battery monitor plugin with the factory."""
    plugin_factory.register(PLUGIN_BATTERY_MONITOR, _create_battery_monitor_view, _create_battery_monitor_model)


class BatteryMonitorWindow(BaseWindow):  # pragma: no cover
    """
    Standalone window for the motor test GUI.

    Used for development and testing.
    """

    def __init__(self, model: BatteryMonitorDataModel) -> None:
        super().__init__()
        self.model = model  # Store model reference for tests
        self.root.title(_("AMC Battery Monitor plugin test window"))
        width = 540
        height = 400
        self.root.geometry(self.calculate_scaled_geometry(width, height))

        self.view = BatteryMonitorView(self.main_frame, model, self)
        self.view.pack(fill="both", expand=True)
        self.view.on_activate()  # Start monitoring when window opens

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self) -> None:
        """Handle window close event."""
        # Attempt to stop any running tests gracefully
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
            "This main is for testing and development only. Usually, the BatteryMonitorView is called from another script"
        )
    )
    parser = FlightController.add_argparse_arguments(parser)
    return add_common_arguments(parser).parse_args()


# pylint: disable=duplicate-code
def main() -> None:  # pragma: no cover
    args = argument_parser()

    state = ApplicationState(args)

    setup_logging(state)

    logging_warning(
        _("This main is for testing and development only, usually the BatteryMonitorView is called from another script")
    )

    # Initialize flight controller and filesystem
    initialize_flight_controller(state)

    try:
        data_model = BatteryMonitorDataModel(state.flight_controller)
        window = BatteryMonitorWindow(data_model)
        window.root.mainloop()

    except Exception as e:  # pylint: disable=broad-exception-caught
        logging_error("Failed to start BatteryMonitorWindow: %(error)s", {"error": e})
        # Show error to user
        showerror(_("Error"), f"Failed to start BatteryMonitorWindow: {e}")
    finally:
        if state.flight_controller:
            state.flight_controller.disconnect()  # Disconnect from the flight controller


if __name__ == "__main__":  # pragma: no cover
    main()
