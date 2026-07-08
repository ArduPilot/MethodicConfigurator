"""
Data model for compass calibration plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import debug as logging_debug
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

    def get_active_compass_ids(self) -> list[int]:
        """
        Return the compass indices that are enabled on the current flight controller.

        ArduPilot stores the enable flags in COMPASS_USE, COMPASS_USE2, COMPASS_USE3, ...
        with COMPASS_USE representing compass 0.
        """
        params = self.flight_controller.fc_parameters
        if not isinstance(params, dict) or params.get("COMPASS_ENABLE", 1) == 0:
            logging_debug(_("Compass calibration preflight: COMPASS_ENABLE disabled or parameters unavailable."))
            return []

        active_compass_ids: list[int] = []
        for param_name, raw_value in params.items():
            if not param_name.startswith("COMPASS_USE") or not raw_value:
                continue

            suffix = param_name.removeprefix("COMPASS_USE")
            if suffix == "":
                active_compass_ids.append(0)
                continue
            if suffix.isdigit():
                active_compass_ids.append(int(suffix) - 1)

        active_compass_ids = sorted(set(active_compass_ids))
        logging_debug(
            _("Compass calibration preflight: enabled compass ids=%(compasses)s, raw flags=%(flags)s"),
            {
                "compasses": active_compass_ids,
                "flags": {
                    key: value for key, value in params.items() if key == "COMPASS_ENABLE" or key.startswith("COMPASS_USE")
                },
            },
        )
        return active_compass_ids

    def start_calibration(self) -> tuple[bool, str]:
        """
        Start the compass calibration process.

        Returns:
            tuple[bool, str]: (success, error_message)

        """
        if not self.is_connected():
            return False, _("Flight controller not connected")

        active_compass_ids = self.get_active_compass_ids()
        if not active_compass_ids:
            error_msg = _(
                "No active compasses are enabled. Set COMPASS_ENABLE=1 and enable at least one COMPASS_USE* parameter."
            )
            logging_warning(error_msg)
            return False, error_msg

        # Delegate to the Front Desk (backend_flightcontroller.py)
        logging_debug(
            _("Compass calibration start requested for active compasses: %(compasses)s"), {"compasses": active_compass_ids}
        )
        success, error_msg = self.flight_controller.start_compass_calibration()
        if success:
            self._is_calibrating = True
            logging_debug(_("Compass calibration start accepted by flight controller."))
        else:
            logging_debug(_("Compass calibration start rejected: %(error)s"), {"error": error_msg})

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
        logging_debug(_("Compass calibration cancel requested."))
        success, error_msg = self.flight_controller.cancel_compass_calibration()

        if success:
            self._is_calibrating = False
            logging_debug(_("Compass calibration cancel accepted by flight controller."))
        else:
            logging_debug(_("Compass calibration cancel rejected: %(error)s"), {"error": error_msg})

        return success, error_msg

    def finish_calibration(self) -> None:
        """Mark the calibration flow as finished."""
        self._is_calibrating = False

    def get_progress(self) -> list[dict[str, int | float | str]]:
        """
        Get the current progress of the compass calibration.

        Returns:
            dict | None: Dictionary containing calibration progress, or None if no data.

        """
        if self.flight_controller.master is None:
            logging_debug(_("Compass calibration progress requested while disconnected."))
            return []

        # logging_debug(_("Compass calibration progress requested from backend."))
        return self.flight_controller.get_compass_calibration_progress()
