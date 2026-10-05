"""
Data model for the RC calibration plugin.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator
SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>
SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Mapping
from copy import deepcopy
from logging import debug as logging_debug
from logging import info as logging_info
from logging import warning as logging_warning
from math import isfinite
from typing import TYPE_CHECKING, Any

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.data_model_parameter_editor import (
    InvalidParameterNameError,
    OperationNotPossibleError,
    ParameterEditor,
    ParameterValueUpdateStatus,
)

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.data_model_ardupilot_parameter import ArduPilotParameter

_RC_INVALID_PWM = 65535  # MAVLink sentinel: channel not available
_RC_CENTER_PWM = 1500  # Default center PWM value
_RC_DISPLAY_CHANNELS = 16

# Each pair is (horizontal axis, vertical axis), ordered left stick then right stick.
RC_STICK_MODES: dict[int, tuple[tuple[str, str], tuple[str, str]]] = {
    1: (("yaw", "pitch"), ("roll", "throttle")),
    2: (("yaw", "throttle"), ("roll", "pitch")),
    3: (("roll", "pitch"), ("yaw", "throttle")),
    4: (("roll", "throttle"), ("yaw", "pitch")),
}

# Presets assume Mode-2 physical slots: right horizontal=1, right vertical=2,
# left vertical=3, left horizontal=4. RCMAP cannot identify a transmitter's physical mode.
RC_MAP_PRESETS: dict[int, dict[str, int]] = {
    1: {"RCMAP_ROLL": 1, "RCMAP_PITCH": 3, "RCMAP_THROTTLE": 2, "RCMAP_YAW": 4},
    2: {"RCMAP_ROLL": 1, "RCMAP_PITCH": 2, "RCMAP_THROTTLE": 3, "RCMAP_YAW": 4},
    3: {"RCMAP_ROLL": 4, "RCMAP_PITCH": 3, "RCMAP_THROTTLE": 2, "RCMAP_YAW": 1},
    4: {"RCMAP_ROLL": 4, "RCMAP_PITCH": 2, "RCMAP_THROTTLE": 3, "RCMAP_YAW": 1},
}


class RCCalibrationDataModel:
    """Data model for RC calibration, backed by MAVLink RC_CHANNELS telemetry."""

    def __init__(self, flight_controller: FlightController, parameter_editor: ParameterEditor | None = None) -> None:
        self.flight_controller = flight_controller
        self._parameter_editor = parameter_editor
        self._is_calibrating = False
        self._channel_min: dict[int, int] = {}  # 0-based channel index → observed minimum PWM
        self._channel_max: dict[int, int] = {}  # 0-based channel index → observed maximum PWM
        self._last_raw: list[int] = []
        self._last_channel_count = 0

    def _preview_parameters(self) -> dict[str, float]:
        """Overlay staged RC values without modifying the downloaded flight-controller cache."""
        parameters = dict(self.flight_controller.fc_parameters)
        if self._parameter_editor is not None:
            for name, parameter in self._parameter_editor.current_step_parameters.items():
                if name.startswith(("RCMAP_", "RC")) or name in ("FLTMODE_CH", "MODE_CH"):
                    parameters[name] = parameter.get_new_value()
        return parameters

    def get_mapping_mode(self) -> int | None:
        """Identify a matching mapping preset, or None for a custom channel assignment."""
        parameters = self._preview_parameters()
        return next(
            (
                mode
                for mode, preset in RC_MAP_PRESETS.items()
                if all(parameters.get(name) == value for name, value in preset.items())
            ),
            None,
        )

    def set_mapping_mode(self, mode: int) -> tuple[bool, str]:
        """Stage a complete RCMAP preset; never send PARAM_SET or alter the FC cache."""
        if mode not in RC_MAP_PRESETS:
            return False, _("Select an RC mapping mode from 1 to 4.")
        success, message = self._stage_parameters(
            RC_MAP_PRESETS[mode], _("RC mapping preset Mode %(mode)d selected in the RC calibration plugin.") % {"mode": mode}
        )
        if success:
            message += " " + _("RC mapping changes require a flight-controller reboot after upload.")
        return success, message

    def _stage_parameters(self, values: Mapping[str, int], reason: str) -> tuple[bool, str]:
        """Validate the whole edit before changing New values, respecting metadata and edit locks."""
        editor = self._parameter_editor
        if editor is None:
            return False, _("Open RC calibration in the parameter editor to stage changes for upload.")
        added: list[str] = []
        changes: list[tuple[ArduPilotParameter, int]] = []
        error = ""
        for name, value in values.items():
            if name not in editor.current_step_parameters:
                try:
                    if not editor.add_parameter_to_current_file(name):
                        error = _("Could not add parameter %(name)s to this step.") % {"name": name}
                        break
                    added.append(name)
                except (InvalidParameterNameError, OperationNotPossibleError) as exc:
                    error = str(exc)
                    break
            parameter = editor.current_step_parameters[name]
            if not parameter.is_editable:
                error = _("Parameter %(name)s is read-only, forced or derived; no values were changed.") % {"name": name}
                break
            result = ParameterEditor.update_parameter_object(deepcopy(parameter), str(value))
            if result.status not in (ParameterValueUpdateStatus.UPDATED, ParameterValueUpdateStatus.UNCHANGED):
                error = result.message or _("Invalid value for parameter %(name)s.") % {"name": name}
                break
            if result.status == ParameterValueUpdateStatus.UPDATED:
                changes.append((parameter, value))
        if error:
            for name in added:
                editor.delete_parameter_from_current_file(name)
            return False, error
        for parameter, value in changes:
            parameter.set_new_value(str(value))
            parameter.set_change_reason(reason)
        return True, _("Changes staged. Press parameter upload to write them to the flight controller.")

    def get_preview_axes(self) -> dict[str, float]:
        """Remap the retained raw input immediately after staged mapping/calibration edits."""
        return {
            axis: self._normalised_axis(self._last_raw, self._last_channel_count, axis, channel)
            for channel, axis in enumerate(("roll", "pitch", "throttle", "yaw"), start=1)
        }

    def is_connected(self) -> bool:
        """Return True when a MAVLink connection is available."""
        return self.flight_controller.master is not None

    @staticmethod
    def channel_limits(parameters: Mapping[str, float], channel_number: int) -> tuple[int, int, int]:
        """Return configured MIN/MAX/TRIM, using display-only defaults for missing or invalid parameters."""
        minimum = parameters.get(f"RC{channel_number}_MIN", 1000)
        maximum = parameters.get(f"RC{channel_number}_MAX", 2000)
        if not (isfinite(minimum) and isfinite(maximum) and 0 < minimum < maximum < _RC_INVALID_PWM):
            minimum, maximum = 1000, 2000
        minimum, maximum = round(minimum), round(maximum)
        if minimum >= maximum:
            minimum, maximum = 1000, 2000
        trim = parameters.get(f"RC{channel_number}_TRIM", (minimum + maximum) / 2)
        if not isfinite(trim) or not minimum <= trim <= maximum:
            trim = (minimum + maximum) / 2
        return round(minimum), round(maximum), round(trim)

    def get_channel_calibration(self) -> list[dict[str, Any]]:
        """Return channel markers, assigned functions, and available RC option choices."""
        parameters = self._preview_parameters()
        channel_functions = self._channel_functions(parameters)
        channels: list[dict[str, Any]] = []
        for index in range(_RC_DISPLAY_CHANNELS):
            channel_number = index + 1
            minimum, maximum, trim = self.channel_limits(parameters, channel_number)
            option_value, choices, option_editable, option_label = self._channel_option_state(channel_number, parameters)
            channels.append(
                {
                    "name": f"CH{channel_number}",
                    "value": None,
                    "min": self._channel_min.get(index, minimum),
                    "max": self._channel_max.get(index, maximum),
                    "trim": trim,
                    "function": channel_functions.get(channel_number, ""),
                    "function_editable": option_editable,
                    "option_label": option_label,
                    "option_value": option_value,
                    "option_choices": choices,
                }
            )
        return channels

    def _channel_option_state(
        self, channel_number: int, parameters: Mapping[str, float]
    ) -> tuple[float, dict[str, str], bool, str]:
        """Return the live RCx_OPTION value, loaded choices, editability and display label."""
        option_name = f"RC{channel_number}_OPTION"
        option_parameter = (
            self._parameter_editor.current_step_parameters.get(option_name) if self._parameter_editor is not None else None
        )
        choices = self._channel_option_choices(option_name)
        option_value = option_parameter.get_new_value() if option_parameter is not None else parameters.get(option_name, 0)
        is_reserved = channel_number in self._reserved_channels(parameters)
        option_editable = not is_reserved and (option_parameter is None or option_parameter.is_editable) and bool(choices)
        option_label = next(
            (label for key, label in choices.items() if self._option_key_matches(key, option_value)),
            str(round(option_value)) if isfinite(option_value) else "",
        )
        return option_value, choices, option_editable, option_label

    def _channel_option_choices(self, option_name: str) -> dict[str, str]:
        """Return the same loaded firmware choices used for display and staging."""
        editor = self._parameter_editor
        if editor is None:
            return {}
        parameter = editor.current_step_parameters.get(option_name)
        if parameter is not None and parameter.choices_dict:
            return parameter.choices_dict
        return editor.get_parameter_choices(option_name)

    @staticmethod
    def _flight_mode_channel(parameters: Mapping[str, float]) -> int:
        """Return the configured flight-mode channel, honoring Rover's MODE_CH parameter."""
        parameter_name = "MODE_CH" if "MODE_CH" in parameters else "FLTMODE_CH"
        default_channel = 8 if parameter_name == "MODE_CH" else 5
        value = parameters.get(parameter_name, default_channel)
        if isfinite(value) and value == int(value) and 0 <= value <= _RC_DISPLAY_CHANNELS:
            return int(value)
        return default_channel

    @staticmethod
    def _option_key_matches(key: str, option_value: float) -> bool:
        """Compare a parameter metadata enum key to its numeric value."""
        try:
            return float(key) == option_value
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _mapped_control_channels(parameters: Mapping[str, float]) -> dict[str, int]:
        """Resolve valid primary-control channels from the effective mapping."""
        mapped_channels: dict[str, int] = {}
        default_channels = {"ROLL": 1, "PITCH": 2, "THROTTLE": 3, "YAW": 4}
        for axis, default_channel in default_channels.items():
            value = parameters.get(f"RCMAP_{axis}", default_channel)
            if isfinite(value) and value == int(value) and 1 <= value <= _RC_DISPLAY_CHANNELS:
                mapped_channels[axis] = int(value)
        return mapped_channels

    @classmethod
    def _reserved_channels(cls, parameters: Mapping[str, float]) -> set[int]:
        """Share primary-control and flight-mode protection between display and staging."""
        channels = set(cls._mapped_control_channels(parameters).values())
        flight_mode_channel = cls._flight_mode_channel(parameters)
        if flight_mode_channel:
            channels.add(flight_mode_channel)
        return channels

    @classmethod
    def _channel_functions(cls, parameters: Mapping[str, float]) -> dict[int, str]:
        """Map channels to their staged RCMAP function and identify the flight-mode channel."""
        channel_functions: dict[int, list[str]] = {}
        for axis, channel in cls._mapped_control_channels(parameters).items():
            channel_functions.setdefault(channel, []).append(_(axis.title()))

        flight_mode_channel = cls._flight_mode_channel(parameters)
        channel_functions.setdefault(flight_mode_channel, []).append(_("Mode"))
        return {channel: " / ".join(functions) for channel, functions in channel_functions.items()}

    def set_channel_option(self, channel_number: int, option_value: str) -> tuple[bool, str]:
        """Stage RCx_OPTION; primary-control and flight-mode channel functions stay locked."""
        parameters = self._preview_parameters()
        if not 1 <= channel_number <= _RC_DISPLAY_CHANNELS:
            return False, _("Select an RC channel from 1 to 16.")
        if channel_number in self._reserved_channels(parameters):
            return False, _("The primary-control and flight-mode channel functions cannot be changed here.")
        try:
            value = int(option_value)
        except ValueError:
            return False, _("Select a valid RC channel option.")
        if self._parameter_editor is not None and not any(
            self._option_key_matches(key, value) for key in self._channel_option_choices(f"RC{channel_number}_OPTION")
        ):
            return False, _("Select a valid RC channel option.")
        return self._stage_parameters(
            {f"RC{channel_number}_OPTION": value},
            _("RC channel %(channel)d option selected in the RC calibration plugin.") % {"channel": channel_number},
        )

    @staticmethod
    def stick_positions(axes: Mapping[str, float], mode: int) -> tuple[tuple[float, float], tuple[float, float]]:
        """
        Return left/right stick positions in the range -1..1 for transmitter Mode 1-4.

        Positive horizontal values mean right and positive vertical values mean up.
        Pitch is inverted because positive pitch is commanded by pulling the stick back.
        """
        positions: list[tuple[float, float]] = []
        for horizontal_axis, vertical_axis in RC_STICK_MODES[mode]:
            horizontal = axes.get(horizontal_axis, 0.0) / 1000
            vertical = axes.get(vertical_axis, 0.0) / 1000
            if vertical_axis == "pitch":
                vertical = -vertical
            positions.append((max(-1.0, min(1.0, horizontal)), max(-1.0, min(1.0, vertical))))
        return positions[0], positions[1]

    def _normalised_axis(self, raw: list[int], channel_count: int, axis: str, default_channel: int) -> float:
        """Map RCMAP-selected PWM to stick travel, respecting configured endpoints and reversal."""
        parameters = self._preview_parameters()
        channel = parameters.get(f"RCMAP_{axis.upper()}", default_channel)
        if not isfinite(channel) or channel != int(channel) or not 1 <= channel <= channel_count:
            return 0.0
        channel_number = int(channel)
        value = raw[channel_number - 1]
        if value in (0, _RC_INVALID_PWM):
            return 0.0
        minimum, maximum, trim = self.channel_limits(parameters, channel_number)
        # Physical throttle-stick center is the endpoint midpoint, not RCn_TRIM (which may be low throttle).
        center = trim if axis != "throttle" and minimum < trim < maximum else (minimum + maximum) / 2
        span = maximum - center if value >= center else center - minimum
        position = (value - center) / span * 1000
        if parameters.get(f"RC{channel_number}_REVERSED", 0) == 1:
            position = -position
        return max(-1000.0, min(1000.0, position))

    def start_calibration(self) -> tuple[bool, str]:
        """Start tracking per-channel min/max PWM values for calibration."""
        if not self.is_connected():
            error_msg = _("Flight controller not connected")
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

    def finish_calibration(self) -> tuple[bool, str]:
        """
        Stage observed RCn_MIN / RCn_MAX / RCn_TRIM for the explicit parameter upload.

        The trim is computed as the midpoint between the observed extremes.
        Only channels that moved during calibration are staged.
        Failed staging retains the observations for retry or cancellation.
        """
        self._is_calibrating = False
        if not self._channel_min:
            logging_warning(_("No RC calibration data recorded — nothing to save"))
            return False, _("No RC calibration data recorded — nothing to save")
        values: dict[str, int] = {}
        for ch_idx, min_val in self._channel_min.items():
            ch_num = ch_idx + 1  # convert to 1-based RC channel number
            max_val = self._channel_max.get(ch_idx, _RC_CENTER_PWM * 2 - min_val)
            if ch_idx in self._channel_max and min_val == max_val:
                logging_info(_("RC%(ch)d did not move; calibration values were not staged"), {"ch": ch_num})
                continue
            # Use a symmetric fallback only when the maximum was never observed.
            trim_val = (min_val + max_val) // 2
            for suffix, value in (("MIN", min_val), ("MAX", max_val), ("TRIM", trim_val)):
                values[f"RC{ch_num}_{suffix}"] = value
            logging_info(
                _("RC%(ch)d: MIN=%(min)d MAX=%(max)d TRIM=%(trim)d"),
                {"ch": ch_num, "min": min_val, "max": max_val, "trim": trim_val},
            )
        if not values:
            self._channel_min.clear()
            self._channel_max.clear()
            message = _("No RC channels moved; no calibration parameters were staged.")
            logging_info(message)
            return True, message
        success, message = self._stage_parameters(values, _("Measured in the RC calibration plugin."))
        if success:
            self._channel_min.clear()
            self._channel_max.clear()
        return success, message

    def get_rc_telemetry(self) -> dict[str, Any]:
        """
        Return live RC telemetry from the flight controller.

        Reads the MAVLink RC_CHANNELS message (non-blocking) and the most
        recent HEARTBEAT (non-blocking) to build the telemetry dict.

        Returns an empty dict when not connected or when no message is
        available yet, which signals the GUI to keep waiting.

        Stick values use staged RCMAP_* and RCn_MIN/MAX/REVERSED, falling back to the parameter cache.
        Trim maps to zero for roll/pitch/yaw; the endpoint midpoint does so for throttle. Defaults are
        CH1=roll, CH2=pitch, CH3=throttle, CH4=yaw and a 1000-2000 us range.
        """
        if self.flight_controller.master is None:
            return {}

        master = self.flight_controller.master
        telemetry: dict[str, Any] = {}

        try:
            latest_rc_msg = master.recv_match(  # pyright: ignore[reportAttributeAccessIssue]
                type="RC_CHANNELS", blocking=False
            )
            latest_hb = master.recv_match(  # pyright: ignore[reportAttributeAccessIssue]
                type="HEARTBEAT", blocking=False
            )

            if latest_rc_msg:
                n_channels = max(0, min(latest_rc_msg.chancount, _RC_DISPLAY_CHANNELS))
                raw: list[int] = [
                    latest_rc_msg.chan1_raw,
                    latest_rc_msg.chan2_raw,
                    latest_rc_msg.chan3_raw,
                    latest_rc_msg.chan4_raw,
                    latest_rc_msg.chan5_raw,
                    latest_rc_msg.chan6_raw,
                    latest_rc_msg.chan7_raw,
                    latest_rc_msg.chan8_raw,
                    latest_rc_msg.chan9_raw,
                    latest_rc_msg.chan10_raw,
                    latest_rc_msg.chan11_raw,
                    latest_rc_msg.chan12_raw,
                    latest_rc_msg.chan13_raw,
                    latest_rc_msg.chan14_raw,
                    latest_rc_msg.chan15_raw,
                    latest_rc_msg.chan16_raw,
                ]

                self._last_raw = raw
                self._last_channel_count = n_channels
                telemetry.update(self.get_preview_axes())

                if self._is_calibrating:
                    for i in range(n_channels):
                        if raw[i] not in (0, _RC_INVALID_PWM):
                            self._channel_min[i] = min(self._channel_min.get(i, raw[i]), raw[i])
                            self._channel_max[i] = max(self._channel_max.get(i, raw[i]), raw[i])

                channels = self.get_channel_calibration()
                for index in range(n_channels):
                    if raw[index] not in (0, _RC_INVALID_PWM):
                        channels[index]["value"] = raw[index]
                telemetry["channels"] = channels

            if latest_hb:
                telemetry["flight_mode"] = str(latest_hb.custom_mode)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logging_debug(_("Error reading MAVLink telemetry: %(error)s"), {"error": str(exc)})

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
