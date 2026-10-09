"""
Data model for battery monitor plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import debug as logging_debug
from logging import warning as logging_warning
from math import inf, isnan, nan

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_flightcontroller_business_logic import (
    get_battery_parameter_prefix,
    get_enabled_battery_ids,
)

# Battery update interval in milliseconds (used for periodic status requests)
BATTERY_UPDATE_INTERVAL_MS = 500


class BatteryMonitorDataModel:
    """
    Data model for battery monitor plugin.

    This class provides business logic for monitoring battery voltage and current,
    reusing backend methods from the flight controller.

    Streaming Resilience:
        This implementation provides automatic recovery if the battery status stream
        is lost. The stream is re-requested whenever get_battery_statuses() indicates
        a lost connection (via message return value). The plugin only marks the stream
        as established when actual data is received, providing resilience against:
        - Initial response delays
        - Stream interruptions and reconnections
        - Communication glitches

    Design:
        - First call to get_battery_statuses() requests periodic updates from the FC
        - Stream request is attempted every call until data is actually received
        - Once data flows, subsequent calls read cached data unless the monitor count changes
        - If stream is lost (indicated by message from get_battery_statuses()), the flag
          resets and re-request happens on next call (automatic recovery)
        - Status indicators (safe/critical/disabled/unavailable) guide user about data validity
    """

    def __init__(self, flight_controller: FlightController) -> None:
        self.flight_controller = flight_controller
        self._got_battery_status = False
        self._battery_status_interval_microseconds: int | None = None

    def get_enabled_battery_ids(self) -> list[int]:
        """Return the configured battery IDs, even while telemetry is unavailable."""
        return get_enabled_battery_ids(self.flight_controller.fc_parameters)

    def is_battery_monitoring_enabled(self) -> bool:
        """
        Check whether any configured battery monitor is enabled.

        Returns:
            bool: True if battery monitoring is enabled, False otherwise

        """
        if self.flight_controller.master is None:
            logging_debug(_("Flight controller not connected, cannot check battery monitoring status."))
            return False
        return self.flight_controller.is_battery_monitoring_enabled()

    def get_battery_statuses(self) -> dict[int, tuple[float, float]] | None:
        """Get recent battery readings keyed by the zero-based MAVLink battery ID."""
        if self.flight_controller.master is None:
            self._got_battery_status = False
            logging_debug(_("Flight controller not connected, cannot get battery status."))
            return None
        if not self.is_battery_monitoring_enabled():
            self._got_battery_status = False
            return None

        # ArduPilot sends one enabled battery per interval, in round-robin order.
        monitor_count = max(1, len(self.get_enabled_battery_ids()))
        interval_microseconds = BATTERY_UPDATE_INTERVAL_MS * 1000 // monitor_count
        if not self._got_battery_status or interval_microseconds != self._battery_status_interval_microseconds:
            self.flight_controller.request_periodic_battery_status(interval_microseconds)
            self._battery_status_interval_microseconds = interval_microseconds

        battery_statuses, message = self.flight_controller.get_battery_statuses()

        if message:
            if self._got_battery_status:
                logging_warning(message)
                self._got_battery_status = False
            else:
                logging_debug(message)
        elif battery_statuses:
            self._got_battery_status = True

        return battery_statuses

    def get_voltage_thresholds(self, battery_id: int) -> tuple[float, float]:
        """
        Get battery voltage thresholds for safety indication.

        Returns:
            tuple[float, float]: (min_voltage, max_voltage) for safe operation

        """
        if self.flight_controller.master is None or not self.flight_controller.fc_parameters:
            logging_warning(_("Flight controller connection required for voltage threshold check"))
            return (nan, nan)

        if battery_id == 0:
            return self.flight_controller.get_voltage_thresholds()
        min_voltage = self.flight_controller.fc_parameters.get(f"{get_battery_parameter_prefix(battery_id)}_ARM_VOLT", 0.0)
        return (min_voltage, inf) if min_voltage > 0 else (nan, nan)

    def get_voltage_status(self, battery_id: int, voltage: float | None) -> str:
        """
        Get the battery voltage status as a string.

        Returns:
            str: "safe", "critical", "disabled", or "unavailable"

        """
        if not self.is_battery_monitoring_enabled():
            return _("disabled")

        if voltage is None or isnan(voltage):
            return _("unavailable")
        min_voltage, max_voltage = self.get_voltage_thresholds(battery_id)

        if isnan(min_voltage) or isnan(max_voltage):
            return _("unavailable")
        if min_voltage < voltage < max_voltage:
            return _("safe")
        return _("critical")

    def get_battery_status_color(self, battery_id: int, voltage: float | None) -> str:
        """
        Get the color code for battery status display.

        Returns:
            str: Color name ("green", "red", or "gray")

        """
        status = self.get_voltage_status(battery_id, voltage)
        if status == _("safe"):
            return "green"
        if status == _("critical"):
            return "red"
        return "gray"

    def refresh_connection_status(self) -> bool:
        """
        Check if flight controller connection is active.

        Returns:
            bool: True if connected, False otherwise

        """
        return self.flight_controller.master is not None

    def stop_monitoring(self) -> None:
        """
        Stop periodic battery status updates.

        Should be called when the plugin is deactivated. This resets the internal flag
        to indicate the plugin is no longer actively monitoring.

        Note: The backend periodic stream intentionally persists after deactivation.
        This design allows:
        - Other components to continue using the battery data stream
        - Quick re-activation without re-requesting the stream
        - Reduced MAVLink traffic when multiple consumers need battery data

        The stream will be re-requested only if needed when the plugin is re-activated
        and the flag indicates no active monitoring.
        """
        if self._got_battery_status:
            self._got_battery_status = False
            logging_debug(_("Battery monitoring stopped"))
