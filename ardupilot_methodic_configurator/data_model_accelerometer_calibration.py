"""
Data model for accelerometer calibration plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 ArduPilot Contributors

SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import debug as logging_debug
from logging import info as logging_info

from pymavlink import mavutil

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

# Human-readable instructions for each calibration position,
# matching the STATUSTEXT messages ArduPilot sends during calibration.
POSITION_LABELS: dict[int, str] = {
    mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEVEL: _("Place vehicle LEVEL and click Continue"),
    mavutil.mavlink.ACCELCAL_VEHICLE_POS_LEFT: _("Place vehicle on its LEFT side and click Continue"),
    mavutil.mavlink.ACCELCAL_VEHICLE_POS_RIGHT: _("Place vehicle on its RIGHT side and click Continue"),
    mavutil.mavlink.ACCELCAL_VEHICLE_POS_NOSEDOWN: _("Place vehicle NOSE DOWN and click Continue"),
    mavutil.mavlink.ACCELCAL_VEHICLE_POS_NOSEUP: _("Place vehicle NOSE UP and click Continue"),
    mavutil.mavlink.ACCELCAL_VEHICLE_POS_BACK: _("Place vehicle on its BACK and click Continue"),
}


class AccelerometerCalibrationDataModel:
    """
    Data model for accelerometer calibration plugin.

    Provides business logic for calibrating accelerometers using MAVLink commands,
    delegating all FC communication to backend_flightcontroller_commands.

    Three calibration modes are supported:
    - Simple (param5=4): one-shot level calibration, no interaction required.
    - Level trim (param5=2): adjusts AHRS_TRIM_* to the current vehicle attitude.
    - Full 6-position (param5=1): interactive; caller must poll
      poll_for_next_position() and call confirm_current_position() for each step.
    """

    def __init__(self, flight_controller: FlightController) -> None:
        """
        Initialize the accelerometer calibration data model.

        Args:
            flight_controller: Backend flight controller interface

        """
        self.flight_controller = flight_controller
        self._current_position: int | None = None  # last ACCELCAL_VEHICLE_POS value from FC

    def is_connected(self) -> bool:
        """Check if flight controller is connected."""
        return self.flight_controller.master is not None

    def start_simple_calibration(self) -> tuple[bool, str]:
        """
        Run a simple one-shot accelerometer calibration.

        The vehicle must be level and stationary. No interaction required.
        Uses MAV_CMD_PREFLIGHT_CALIBRATION with param5=4.

        Returns:
            tuple[bool, str]: (success, message)

        """
        if not self.is_connected():
            return False, _("Flight controller not connected")
        success, error_msg = self.flight_controller.start_accel_calibration_simple()
        if success:
            logging_info(_("Simple accelerometer calibration completed"))
            return True, _("Calibration successful")
        return False, error_msg or _("Calibration failed")

    def start_level_calibration(self) -> tuple[bool, str]:
        """
        Level-trim the accelerometers to the vehicle's current attitude.

        Sets AHRS_TRIM_* parameters. The vehicle must be placed level.
        Uses MAV_CMD_PREFLIGHT_CALIBRATION with param5=2.

        Returns:
            tuple[bool, str]: (success, message)

        """
        if not self.is_connected():
            return False, _("Flight controller not connected")
        success, error_msg = self.flight_controller.start_accel_calibration_level()
        if success:
            logging_info(_("Level calibration completed"))
            return True, _("Level calibration successful")
        return False, error_msg or _("Level calibration failed")

    def start_full_calibration(self) -> tuple[bool, str]:
        """
        Begin the interactive 6-position accelerometer calibration.

        Sends MAV_CMD_PREFLIGHT_CALIBRATION with param5=1 and returns immediately.
        The caller must then drive the protocol by polling poll_for_next_position()
        and calling confirm_current_position() for each of the six positions.

        Returns:
            tuple[bool, str]: (success, message)

        """
        if not self.is_connected():
            return False, _("Flight controller not connected")
        self._current_position = None
        success, error_msg = self.flight_controller.send_accel_calibration_full_start()
        if success:
            return True, _("Calibration started - follow on-screen instructions")
        return False, error_msg or _("Failed to start calibration")

    def poll_for_next_position(self) -> int | None:
        """
        Non-blocking poll for the next position requested by the FC.

        Call this repeatedly (e.g. from a tkinter after() loop) after
        start_full_calibration() returns True.

        Returns:
            int: ACCELCAL_VEHICLE_POS enum value (1-6) if the FC is asking for a
                 new position, ACCELCAL_VEHICLE_POS_SUCCESS (16777215) on success,
                 ACCELCAL_VEHICLE_POS_FAILED (16777216) on failure, or None if no
                 message has arrived yet.

        """
        pos = self.flight_controller.poll_accel_cal_vehicle_pos(timeout=0.05)
        if pos is not None:
            self._current_position = pos
            logging_debug(_("FC requested calibration position: %d"), pos)
        return pos

    def get_position_label(self, position: int) -> str:
        """Return a human-readable instruction for the given ACCELCAL_VEHICLE_POS value."""
        return POSITION_LABELS.get(position, _("Unknown position %d") % position)

    def is_calibration_complete(self, position: int) -> bool:
        """Return True if position signals end of calibration (success or failure)."""
        return position in (
            mavutil.mavlink.ACCELCAL_VEHICLE_POS_SUCCESS,
            mavutil.mavlink.ACCELCAL_VEHICLE_POS_FAILED,
        )

    def is_calibration_successful(self, position: int) -> bool:
        """Return True if position signals successful completion."""
        return bool(position == mavutil.mavlink.ACCELCAL_VEHICLE_POS_SUCCESS)

    def confirm_current_position(self) -> tuple[bool, str]:
        """
        Confirm to the FC that the vehicle is now in the requested position.

        Call this after the user indicates readiness. Sends COMMAND_LONG with
        MAV_CMD_ACCELCAL_VEHICLE_POS back to the FC.

        Returns:
            tuple[bool, str]: (success, message)

        """
        if self._current_position is None:
            return False, _("No position has been requested by the flight controller yet")
        if self._current_position in (
            mavutil.mavlink.ACCELCAL_VEHICLE_POS_SUCCESS,
            mavutil.mavlink.ACCELCAL_VEHICLE_POS_FAILED,
        ):
            return False, _("Calibration has already completed")
        success, error_msg = self.flight_controller.confirm_accel_vehicle_pos(self._current_position)
        if success:
            logging_debug(_("Confirmed calibration position %d"), self._current_position)
        return success, error_msg or _("Failed to send position confirmation")
