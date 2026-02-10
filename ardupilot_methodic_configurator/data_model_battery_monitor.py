"""
Data model for battery monitor plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import debug as logging_debug
from logging import warning as logging_warning
from math import isnan, nan
from typing import TYPE_CHECKING, Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor

# Battery update interval in milliseconds (used for periodic status requests)
BATTERY_UPDATE_INTERVAL_MS = 500


class BatteryMonitorDataModel:
    """
    Data model for battery monitor plugin.

    This class provides business logic for monitoring battery voltage and current,
    reusing backend methods from the flight controller.

    Streaming Resilience:
        This implementation provides automatic recovery if the battery status stream
        is lost. The stream is re-requested whenever get_battery_status() indicates
        a lost connection (via message return value). The plugin only marks the stream
        as established when actual data is received, providing resilience against:
        - Initial response delays
        - Stream interruptions and reconnections
        - Communication glitches

    Design:
        - First call to get_battery_status() requests periodic updates from the FC
        - Stream request is attempted every call until data is actually received
        - Once data flows, _got_battery_status = True and subsequent calls read cached data
        - If stream is lost (indicated by message from get_battery_status()), the flag
          resets and re-request happens on next call (automatic recovery)
        - Status indicators (safe/critical/disabled/unavailable) guide user about data validity
    """

    def __init__(
        self,
        flight_controller: FlightController,
        parameter_editor: Optional["ParameterEditor"] = None,
    ) -> None:
        """
        Initialize the battery monitor data model.

        Args:
            flight_controller: Backend flight controller interface
            parameter_editor: Optional parameter editor for uploading parameters

        """
        self.flight_controller = flight_controller
        self.parameter_editor = parameter_editor
        self._got_battery_status = False

    def is_battery_monitoring_enabled(self) -> bool:
        """
        Check if battery monitoring is enabled (BATT_MONITOR != 0).

        Returns:
            bool: True if battery monitoring is enabled, False otherwise

        """
        if self.flight_controller.master is None:
            logging_warning(_("Flight controller not connected, cannot check battery monitoring status."))
            return False
        return self.flight_controller.is_battery_monitoring_enabled()

    def get_battery_status(self) -> Optional[tuple[float, float]]:
        """
        Get the current battery voltage and current.

        This method requests periodic BATTERY_STATUS messages from the flight controller
        on the first call and caches subsequent reads. The flight controller is assumed
        to maintain the periodic stream at 500ms intervals after the initial request.

        Returns:
            Optional[tuple[float, float]]:
                - (voltage, current) in volts and amps when data is available from the stream
                - None when flight controller is not connected
                - None when battery monitoring is disabled (BATT_MONITOR == 0)
                - None when stream is not yet established or data not yet received

        Assumptions:
            - The flight controller maintains the periodic BATTERY_STATUS stream after
              request_periodic_battery_status() succeeds
            - Battery monitoring must be enabled (BATT_MONITOR != 0) for data to be available
            - Once a request succeeds AND data is received, subsequent calls will return
              cached data from the maintained stream
            - If the stream is lost (indicated by a message on get_battery_status), the
              plugin will automatically re-request it on the next call
            - Initial responses may have delays, so success is only confirmed when
              actual data is returned (message is None)
            - Duplicate stream requests (if made before _got_battery_status is set to True)
              are safe and handled gracefully by the backend

        """
        if self.flight_controller.master is None:
            logging_warning(_("Flight controller not connected, cannot get battery status."))
            return None

        if not self.is_battery_monitoring_enabled():
            logging_debug(_("Battery monitoring disabled, cannot get battery status."))
            return None

        if not self._got_battery_status:
            self.flight_controller.request_periodic_battery_status(BATTERY_UPDATE_INTERVAL_MS * 1000)

        battery_status, message = self.flight_controller.get_battery_status()
        if message:
            logging_warning(message)
            # Reset flag to trigger re-request on next call (automatic recovery)
            self._got_battery_status = False
        elif battery_status is not None:
            # Only mark stream as established when we receive actual data
            self._got_battery_status = True

        return battery_status

    def get_voltage_thresholds(self) -> tuple[float, float]:
        """
        Get battery voltage thresholds for safety indication.

        Returns:
            tuple[float, float]: (min_voltage, max_voltage) for safe operation

        """
        if self.flight_controller.master is None or not self.flight_controller.fc_parameters:
            logging_warning(_("Flight controller connection required for voltage threshold check"))
            return (nan, nan)

        return self.flight_controller.get_voltage_thresholds()

    def get_voltage_status(self) -> str:
        """
        Get the battery voltage status as a string.

        Returns:
            str: "safe", "critical", "disabled", or "unavailable"

        """
        if not self.is_battery_monitoring_enabled():
            return _("disabled")

        battery_status = self.get_battery_status()
        if battery_status is None:
            return _("unavailable")

        voltage, _current = battery_status
        min_voltage, max_voltage = self.get_voltage_thresholds()

        if isnan(min_voltage) or isnan(max_voltage):
            return _("unavailable")
        if min_voltage < voltage < max_voltage:
            return _("safe")
        return _("critical")

    def get_battery_status_color(self) -> str:
        """
        Get the color code for battery status display.

        Returns:
            str: Color name ("green", "red", or "gray")

        """
        status = self.get_voltage_status()
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
