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
from tkinter import Frame, ttk
from tkinter.messagebox import showerror
from typing import TYPE_CHECKING, Optional, Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.__main__ import (
    ApplicationState,
    initialize_flight_controller,
    setup_logging,
)
from ardupilot_methodic_configurator.common_arguments import add_common_arguments
from ardupilot_methodic_configurator.data_model_battery_monitor import (
    BATTERY_UPDATE_INTERVAL_MS,
    BatteryMonitorDataModel,
)
from ardupilot_methodic_configurator.data_model_par_dict import ParDict
from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_show import show_tooltip
from ardupilot_methodic_configurator.plugin_constants import PLUGIN_BATTERY_MONITOR
from ardupilot_methodic_configurator.plugin_factory import plugin_factory

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import (
        ParameterEditorUiServices,
    )


class BatteryMonitorView(Frame):
    """GUI for battery monitor plugin."""

    def __init__(
        self,
        parent: Union[tk.Frame, ttk.Frame],
        model: BatteryMonitorDataModel,
        base_window: BaseWindow,
        ui_services: Optional["ParameterEditorUiServices"] = None,
    ) -> None:
        """
        Initialize the battery monitor view.

        Args:
            parent: Parent widget
            model: Data model for battery monitoring
            base_window: Parent BaseWindow instance
            ui_services: Optional UI services for testing. If None, will use base_window.ui.

        """
        super().__init__(parent)
        self.model = model
        self.base_window = base_window
        # Reuse UI services from base window if not explicitly provided
        self.ui = ui_services if ui_services is not None else getattr(base_window, "ui", None)
        self._timer_id: Optional[str] = None
        self.voltage_value_label: ttk.Label
        self.current_value_label: ttk.Label
        self.upload_button: ttk.Button

        # Create UI components (labels initialized in _setup_ui)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True)

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
            "  • Green: Safe voltage range [BATT_ARM_VOLT, MOT_BAT_VOLT_MAX]\n"
            "  • Red: Critical voltage (outside safe range)\n"
            "  • Gray: Battery monitoring disabled or unavailable"
        )
        info_label = ttk.Label(main_frame, text=info_text, justify="left")
        info_label.pack(pady=(0, 30))

        # Container for voltage and current side by side
        battery_display_container = ttk.Frame(main_frame)
        battery_display_container.pack(pady=10)

        # Voltage display (left side)
        voltage_container = ttk.Frame(battery_display_container)
        voltage_container.pack(side="left", padx=20)
        ttk.Label(voltage_container, text=_("Voltage:"), font=("TkDefaultFont", 12)).pack(side="left", padx=5)
        self.voltage_value_label = ttk.Label(
            voltage_container,
            text=_("N/A"),
            font=("TkDefaultFont", 16, "bold"),
        )
        self.voltage_value_label.pack(side="left", padx=5)

        # Current display (right side)
        current_container = ttk.Frame(battery_display_container)
        current_container.pack(side="right", padx=20)
        ttk.Label(current_container, text=_("Current:"), font=("TkDefaultFont", 12)).pack(side="left", padx=5)
        self.current_value_label = ttk.Label(
            current_container,
            text=_("N/A"),
            font=("TkDefaultFont", 16, "bold"),
        )
        self.current_value_label.pack(side="left", padx=5)

        # Upload button (only shown if parameter editor is available)
        if self.model.parameter_editor is not None:
            button_container = ttk.Frame(main_frame)
            button_container.pack(pady=20)
            self.upload_button = ttk.Button(
                button_container,
                text=_("Upload selected params to FC"),
                command=self._on_upload_button_clicked,
            )
            self.upload_button.pack()
            show_tooltip(
                self.upload_button,
                _(
                    "Upload selected parameters to the flight controller and stay on the current "
                    "intermediate parameter file\nIt will reset the FC if necessary, re-download "
                    "all parameters and validate their value"
                ),
            )

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
            voltage_text = f"{voltage:.2f} V"
            current_text = f"{current:.2f} A"
            return voltage_text, current_text
        return _("N/A"), _("N/A")

    def _on_upload_button_clicked(self) -> None:
        """Handle upload button click event."""
        if self.ui is None:
            showerror(
                _("Error"),
                _("UI services not available. Cannot upload parameters."),
            )
            return

        gui_complexity = getattr(self.base_window, "gui_complexity", "simple")
        parameter_editor_table = getattr(self.base_window, "parameter_editor_table", None)

        if parameter_editor_table is None or self.model.parameter_editor is None:
            showerror(_("Error"), _("Parameter editor not available."))
            return

        # Get selected params through the data model
        try:
            selected_params: ParDict = parameter_editor_table.get_upload_selected_params(gui_complexity)
        except Exception as e:  # pylint: disable=broad-exception-caught
            showerror(_("Error"), str(e))
            return

        # Check upload preconditions
        precondition_payload: dict[str, object] = dict(selected_params)
        if not self.model.parameter_editor.ensure_upload_preconditions(precondition_payload, self.ui.show_warning):
            return

        self.upload_selected_params(selected_params)

        # Refresh the parameter editor table to show updated FC values
        if parameter_editor_table:
            show_only_differences_var = getattr(self.base_window, "show_only_differences", None)
            show_only_differences = show_only_differences_var.get() if show_only_differences_var else False
            parameter_editor_table.repopulate_table(show_only_differences=show_only_differences, gui_complexity=gui_complexity)

    def upload_selected_params(self, selected_params: ParDict) -> None:
        """
        Upload selected parameters to flight controller with progress feedback.

        Args:
            selected_params: Dictionary of parameters to upload

        """
        if self.ui is None:
            showerror(
                _("Error"),
                _("UI services not available. Cannot upload parameters."),
            )
            logging_error("UI services not available for parameter upload")
            return

        if self.model.parameter_editor is None:
            showerror(_("Error"), _("Parameter editor not available."))
            logging_error("Parameter editor not available for parameter upload")
            return

        try:
            self.ui.upload_params_with_progress(
                self.base_window.root,
                self.model.parameter_editor.upload_selected_params_workflow,
                selected_params,
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            self.ui.show_error(_("Upload Error"), f"{_('Failed to upload parameters:')} {e}")
            logging_error("Parameter upload failed: %(error)s", {"error": e})

    def _schedule_next_update(self) -> None:
        """Schedule the next battery status update."""
        self._timer_id = self.after(BATTERY_UPDATE_INTERVAL_MS, self._periodic_update)

    def _periodic_update(self) -> None:
        """Periodic update callback."""
        if self.model.refresh_connection_status():
            self._update_battery_status()
        self._schedule_next_update()

    def on_activate(self) -> None:
        """
        Called when the plugin becomes active (visible).

        Starts periodic updates and refreshes battery status to ensure the display is up-to-date.
        """
        if self.model.refresh_connection_status():
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
    parent: Union[tk.Frame, ttk.Frame],
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


def register_battery_monitor_plugin() -> None:
    """Register the battery monitor plugin with the factory."""
    plugin_factory.register(PLUGIN_BATTERY_MONITOR, _create_battery_monitor_view)


class BatteryMonitorWindow(BaseWindow):  # pragma: no cover
    """
    Standalone window for the motor test GUI.

    Used for development and testing.
    """

    def __init__(self, model: BatteryMonitorDataModel) -> None:
        super().__init__()
        self.model = model  # Store model reference for tests
        self.root.title(_("AMC Battery Monitor plugin test window"))
        width = 480
        height = 250
        self.root.geometry(str(width) + "x" + str(height))

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
        data_model = BatteryMonitorDataModel(state.flight_controller, None)
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
