"""
Data model for the RC calibration plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator
SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import debug as logging_debug
from logging import info as logging_info
from logging import warning as logging_warning
from typing import Any

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

_RC_INVALID_PWM = 65535  # MAVLink sentinel: channel not available
_RC_CENTER_PWM = 1500  # Default center PWM value
_RC_MAX_CHANNELS = 18  # ArduPilot supports up to 18 RC channels


class RCCalibrationDataModel:
    """Data model for RC calibration, backed by MAVLink RC_CHANNELS telemetry."""

    def __init__(self, flight_controller: FlightController) -> None:
        self.flight_controller = flight_controller
        self._is_calibrating = False
        self._channel_min: dict[int, int] = {}  # 0-based channel index → observed minimum PWM
        self._channel_max: dict[int, int] = {}  # 0-based channel index → observed maximum PWM

    def is_connected(self) -> bool:
        """Return True when a MAVLink connection is available."""
        return self.flight_controller.master is not None

    def start_calibration(self) -> tuple[bool, str]:
        """Start tracking per-channel min/max PWM values for calibration."""
        if not self.is_connected():
            error_msg = _("Not connected to flight controller")
            return False, error_msg
        self._is_calibrating = True
        self._channel_min.clear()
        self._channel_max.clear()
        logging_info(_("RC calibration started — move all sticks and switches to their extremes"))
        return True, ""

    def cancel_calibration(self) -> tuple[bool, str]:
        """Cancel calibration without writing any parameters to the FC."""
        self._is_calibrating = False
        self._channel_min.clear()
        self._channel_max.clear()
        logging_info(_("RC calibration cancelled"))
        return True, ""

    def finish_calibration(self) -> None:
        """
        Write observed min/max values as RCn_MIN / RCn_MAX / RCn_TRIM to the FC.

        The trim is computed as the midpoint between the observed extremes.
        Only channels that received at least one valid reading are written.
        """
        self._is_calibrating = False
        if not self._channel_min:
            logging_warning(_("No RC calibration data recorded — nothing to save"))
            return
        for ch_idx, min_val in self._channel_min.items():
            ch_num = ch_idx + 1  # convert to 1-based RC channel number
            max_val = self._channel_max.get(ch_idx, _RC_CENTER_PWM * 2 - min_val)
            trim_val = (min_val + max_val) // 2
            self.flight_controller.set_param(f"RC{ch_num}_MIN", float(min_val))
            self.flight_controller.set_param(f"RC{ch_num}_MAX", float(max_val))
            self.flight_controller.set_param(f"RC{ch_num}_TRIM", float(trim_val))
            logging_info(
                _("RC%(ch)d: MIN=%(min)d MAX=%(max)d TRIM=%(trim)d"),
                {"ch": ch_num, "min": min_val, "max": max_val, "trim": trim_val},
            )
        self._channel_min.clear()
        self._channel_max.clear()

    def get_rc_telemetry(self) -> dict[str, Any]:
        """
        Return live RC telemetry from the flight controller.

        Reads the MAVLink RC_CHANNELS message (non-blocking) and the most
        recent HEARTBEAT (non-blocking) to build the telemetry dict.

        Returns an empty dict when not connected or when no message is
        available yet, which signals the GUI to keep waiting.

        The stick values (roll / pitch / throttle / yaw) are mapped from
        the PWM range 1000-2000 us to the normalised range -1000 ... +1000
        using the default ArduPilot channel assignment:
            CH1 = roll, CH2 = pitch, CH3 = throttle, CH4 = yaw.
        """
        if self.flight_controller.master is None:
            return {}

        master = self.flight_controller.master
        telemetry: dict[str, Any] = {}

        try:
            rc_msg = master.recv_match(  # pyright: ignore[reportAttributeAccessIssue]
                type="RC_CHANNELS", blocking=False
            )
            if rc_msg:
                n_channels = min(rc_msg.chancount, _RC_MAX_CHANNELS)
                raw: list[int] = [
                    rc_msg.chan1_raw,
                    rc_msg.chan2_raw,
                    rc_msg.chan3_raw,
                    rc_msg.chan4_raw,
                    rc_msg.chan5_raw,
                    rc_msg.chan6_raw,
                    rc_msg.chan7_raw,
                    rc_msg.chan8_raw,
                    rc_msg.chan9_raw,
                    rc_msg.chan10_raw,
                    rc_msg.chan11_raw,
                    rc_msg.chan12_raw,
                    rc_msg.chan13_raw,
                    rc_msg.chan14_raw,
                    rc_msg.chan15_raw,
                    rc_msg.chan16_raw,
                    rc_msg.chan17_raw,
                    rc_msg.chan18_raw,
                ]
                telemetry["channels"] = [
                    {"name": f"CH{i + 1}", "value": raw[i]} for i in range(n_channels) if raw[i] != _RC_INVALID_PWM
                ]

                # Default channel-to-axis mapping (CH1=roll, CH2=pitch, CH3=throttle, CH4=yaw)
                for idx, axis in enumerate(["roll", "pitch", "throttle", "yaw"]):
                    if idx < n_channels and raw[idx] != _RC_INVALID_PWM:
                        # Map PWM 1000-2000 us -> -1000 ... +1000
                        telemetry[axis] = float((raw[idx] - _RC_CENTER_PWM) * 2)
                    else:
                        telemetry[axis] = 0.0

                if self._is_calibrating:
                    for i in range(n_channels):
                        if raw[i] != _RC_INVALID_PWM:
                            self._channel_min[i] = min(self._channel_min.get(i, raw[i]), raw[i])
                            self._channel_max[i] = max(self._channel_max.get(i, raw[i]), raw[i])
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logging_debug(_("Error reading RC_CHANNELS: %(error)s"), {"error": str(exc)})

        try:
            hb = master.recv_match(  # pyright: ignore[reportAttributeAccessIssue]
                type="HEARTBEAT", blocking=False
            )
            if hb:
                telemetry["flight_mode"] = str(hb.custom_mode)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logging_debug(_("Error reading HEARTBEAT: %(error)s"), {"error": str(exc)})

        return telemetry

    def get_flight_mode(self) -> str:
        """Return the current flight mode string from the most recent HEARTBEAT message."""
        if self.flight_controller.master is None:
            return _("Not connected")
        try:
            hb = self.flight_controller.master.recv_match(  # pyright: ignore[reportAttributeAccessIssue]
                type="HEARTBEAT", blocking=False
            )
            if hb:
                return str(hb.custom_mode)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logging_debug(_("Error reading HEARTBEAT: %(error)s"), {"error": str(exc)})
        return _("No Data")
