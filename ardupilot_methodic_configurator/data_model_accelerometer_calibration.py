"""
Data model for accelerometer calibration plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 ArduPilot Contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import debug as logging_debug
from logging import warning as logging_warning
from typing import Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController


class AccelerometerCalibrationDataModel:
    """
    Data model for accelerometer calibration plugin.

    Provides business logic for calibrating accelerometers using MAVLink commands.
    """

    def __init__(self, flight_controller: FlightController) -> None:
        """
        Initialize the accelerometer calibration data model.

        Args:
            flight_controller: Backend flight controller interface
        """
        self.flight_controller = flight_controller

    def is_connected(self) -> bool:
        """Check if flight controller is connected."""
        return self.flight_controller.master is not None

    def start_simple_calibration(self) -> tuple[bool, str]:
        """
        Start simple accelerometer calibration (level only).

        Returns:
            tuple[bool, str]: (success, message)
        """
        master = self.flight_controller.master
        if master is None:
            return False, _("Flight controller not connected")

        try:
            # MAV_CMD_PREFLIGHT_CALIBRATION (241), param5=1 for simple accel
            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                241,  # MAV_CMD_PREFLIGHT_CALIBRATION
                0,    # confirmation
                0,    # param1: gyro
                0,    # param2: mag
                0,    # param3: pressure
                0,    # param4: radio
                1,    # param5: accel simple
                0,    # param6: reserved
                0,    # param7: reserved
            )
            logging_debug(_("Sent simple accelerometer calibration command"))
            return True, _("Calibration started - keep vehicle level")
        except Exception as e:  # noqa: BLE001
            logging_warning(_("Failed to start calibration: %s"), e)
            return False, _("Command failed: %s") % str(e)

    def start_full_calibration(self) -> tuple[bool, str]:
        """
        Start full 6-position accelerometer calibration.

        Returns:
            tuple[bool, str]: (success, message)
        """
        master = self.flight_controller.master
        if master is None:
            return False, _("Flight controller not connected")

        try:
            # MAV_CMD_PREFLIGHT_CALIBRATION (241), param5=4 for full accel
            master.mav.command_long_send(
                master.target_system,
                master.target_component,
                241,  # MAV_CMD_PREFLIGHT_CALIBRATION
                0,    # confirmation
                0,    # param1: gyro
                0,    # param2: mag
                0,    # param3: pressure
                0,    # param4: radio
                4,    # param5: accel full (6-position)
                0,    # param6: reserved
                0,    # param7: reserved
            )
            logging_debug(_("Sent full accelerometer calibration command"))
            return True, _("Calibration started - follow on-screen instructions")
        except Exception as e:  # noqa: BLE001
            logging_warning(_("Failed to start calibration: %s"), e)
            return False, _("Command failed: %s") % str(e)
