"""
Data model for compass calibration plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import debug as logging_debug
from logging import warning as logging_warning

from pymavlink import mavutil

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.backend_flightcontroller_commands import CompassCalibrationUpdate


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
        self._pending_intervals: dict[int, int] = {}
        self._stream_connection = None

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

        # Finish any outstanding restore before capturing the rates for a new calibration.
        self._restore_message_streams()
        if self._pending_intervals:
            return False, _("Could not restore previous compass telemetry intervals")
        self._stream_connection = self.flight_controller.master
        for message_id in (mavutil.mavlink.MAVLINK_MSG_ID_MAG_CAL_PROGRESS, mavutil.mavlink.MAVLINK_MSG_ID_MAG_CAL_REPORT):
            interval = self.flight_controller.get_message_interval(message_id)
            if interval is None:
                logging_warning("Could not capture telemetry interval for message %s, will restore the default", message_id)
                interval = 0
            self._pending_intervals[message_id] = interval
            success, error, rejected = self.flight_controller.set_message_interval(message_id, 200_000)
            if not success:
                # The rate may have changed even if its ACK was lost.
                if rejected:
                    del self._pending_intervals[message_id]
                self._restore_message_streams()
                logging_warning("Could not request compass telemetry for message %s: %s", message_id, error)
                return False, _("Could not enable compass calibration telemetry, calibration not started")

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
            self._restore_message_streams()

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
            self._restore_message_streams()
            logging_debug(_("Compass calibration cancel accepted by flight controller."))
        else:
            logging_debug(_("Compass calibration cancel rejected: %(error)s"), {"error": error_msg})

        return success, error_msg

    def finish_calibration(self) -> None:
        """Mark the calibration flow as finished."""
        self._is_calibrating = False
        self._restore_message_streams()

    def _restore_message_streams(self) -> None:
        """Retry each pending restore only on the original connection; discard them if the link changed."""
        if not self._pending_intervals:
            return
        if self.flight_controller.master is not self._stream_connection:
            logging_warning("Discarding telemetry intervals captured on a previous connection")
            self._pending_intervals.clear()
            self._stream_connection = None
            return
        for message_id, interval in list(self._pending_intervals.items()):
            success, error_msg, _rejected = self.flight_controller.set_message_interval(message_id, interval)
            if success:
                del self._pending_intervals[message_id]
            else:
                logging_warning("Could not restore telemetry interval for message %s: %s", message_id, error_msg)
        if not self._pending_intervals:
            self._stream_connection = None

    def get_progress(self) -> list[CompassCalibrationUpdate]:
        """
        Get the current progress of the compass calibration.

        Returns:
            list[CompassCalibrationUpdate]: Calibration updates, or an empty list if no data is available.

        """
        if self.flight_controller.master is None:
            logging_debug(_("Compass calibration progress requested while disconnected."))
            return []

        # logging_debug(_("Compass calibration progress requested from backend."))
        return self.flight_controller.get_compass_calibration_progress()
