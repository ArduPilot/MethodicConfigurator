"""
Data model for the level calibration plugin.

This file is part of ArduPilot Methodic Configurator.
https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Amilcar do Carmo Lucas

SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import info as logging_info

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController


class LevelCalibrationDataModel:
    """Run the MAVLink level-trim calibration that sets ``AHRS_TRIM_*``."""

    def __init__(self, flight_controller: FlightController) -> None:
        self.flight_controller = flight_controller

    def start_level_calibration(self) -> tuple[bool, str]:
        """Start level trim; poll ``poll_level_calibration`` for the eventual result."""
        if self.flight_controller.master is None:
            return False, _("Flight controller not connected")
        success, error_msg = self.flight_controller.start_accel_calibration_level()
        if success:
            return True, _("Level calibration started")
        return False, error_msg or _("Failed to start level calibration")

    def poll_level_calibration(self) -> tuple[bool, str] | None:
        """Poll the flight controller once; return None while calibration is in progress."""
        result = self.flight_controller.poll_accel_calibration_level()
        if result is None:
            return None
        success, error_msg = result
        if success:
            logging_info(_("Level calibration completed"))
            return True, _("Level calibration successful")
        return False, error_msg or _("Level calibration failed")

    def abort_level_calibration(self) -> None:
        """Release an exchange when the level calibration view closes."""
        self.flight_controller.abort_accel_calibration_level()
