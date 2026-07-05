"""
Data model for compass calibration plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import warning as logging_warning

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController


class CompassCalibrationDataModel:
    """
    Data model for compass calibration plugin.

    Provides business logic for calibrating compasses using MAVLink commands,
    acting as a translator between the GUI and the raw FlightController backend.
    """

    def __init__(self, flight_controller: FlightController) -> None:
        """
        Initialize the compass calibration data model.

        Args:
            flight_controller: Backend flight controller interface

        """
        self.flight_controller = flight_controller
        self._is_calibrating = False

    def is_connected(self) -> bool:
        """Check if the flight controller is actively connected."""
        if self.flight_controller.master is None:
            logging_warning(_("Flight controller not connected, cannot check compass status."))
            return False
        return True

    def start_calibration(self) -> tuple[bool, str]:
        """
        Start the compass calibration process.

        Returns:
            tuple[bool, str]: (success, error_message)

        """
        if not self.is_connected():
            return False, _("Flight controller not connected")

        # Delegate to the Front Desk (backend_flightcontroller.py)
        success, error_msg = self.flight_controller.start_compass_calibration()
        if success:
            self._is_calibrating = True

        return success, error_msg

    def cancel_calibration(self) -> tuple[bool, str]:
        """
        Cancel the ongoing compass calibration process.

        Returns:
            tuple[bool, str]: (success, error_message)

        """
        if not self.is_connected():
            return False, _("Flight controller not connected")

        # Delegate to the Front Desk (backend_flightcontroller.py)
        success, error_msg = self.flight_controller.cancel_compass_calibration()

        if success:
            self._is_calibrating = False

        return success, error_msg

    def get_progress(self) -> dict[str, int | float | str] | None:
        """
        Get the current progress of the compass calibration.

        Returns:
            dict | None: Dictionary containing calibration progress, or None if no data.

        """
        if not self.is_connected():
            return None
        return self.flight_controller.get_compass_calibration_progress()
