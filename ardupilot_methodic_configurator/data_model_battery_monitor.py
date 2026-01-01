"""
Data model for battery monitor plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import debug as logging_debug
from logging import warning as logging_warning
from math import nan
from typing import Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController


class BatteryMonitorDataModel:
    """
    Data model for battery monitor plugin.

    This class provides business logic for monitoring battery voltage and current,
    reusing backend methods from the flight controller.
    """

    def __init__(self, flight_controller: FlightController) -> None:
        """
        Initialize the battery monitor data model.

        Args:
            flight_controller: Backend flight controller interface

        """
        self.flight_controller = flight_controller
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

        Returns:
            Optional[tuple[float, float]]: (voltage, current) in volts and amps,
                                         or None if not available

        """
        if self.flight_controller.master is None:
            logging_warning(_("Flight controller not connected, cannot get battery status."))
            return None

        if not self.is_battery_monitoring_enabled():
            logging_debug(_("Battery monitoring disabled, cannot get battery status."))
            return None

        if not self._got_battery_status:
            self.flight_controller.request_periodic_battery_status(500000)

        battery_status, message = self.flight_controller.get_battery_status()
        if message:
            logging_debug(message)
        else:
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
            return "disabled"

        battery_status = self.get_battery_status()
        if battery_status is None:
            return "unavailable"

        voltage, _current = battery_status
        min_voltage, max_voltage = self.get_voltage_thresholds()

        if min_voltage < voltage < max_voltage:
            return "safe"
        return "critical"

    def get_battery_status_color(self) -> str:
        """
        Get the color code for battery status display.

        Returns:
            str: Color name ("green", "red", or "gray")

        """
        status = self.get_voltage_status()
        if status == "safe":
            return "green"
        if status == "critical":
            return "red"
        return "gray"

    def refresh_connection_status(self) -> bool:
        """
        Check if flight controller connection is active.

        Returns:
            bool: True if connected, False otherwise

        """
        return self.flight_controller.master is not None
