"""
Data model for the plane and tilt-rotor control surface setup plugin.

Guides the user through checking servo directions (FBWA), RC input directions,
servo trim and travel (MANUAL) and, on tilt-rotor QuadPlanes, the forward-flight
(MANUAL) and hover (QSTABILIZE) tilt servo end points.

All adjustments are written live to the flight controller so the surfaces move
while the user edits them. Saving verifies the written values and stages them in
the current configuration step so they are traceable in the vehicle project.

References:
    https://ardupilot.org/plane/docs/guide-four-channel-plane.html
    https://ardupilot.org/plane/docs/quadplane-tips.html#tilt-rotor-setup
    https://ardupilot.org/plane/docs/guide-tilt-rotor.html

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2026 Allister779

SPDX-License-Identifier: GPL-3.0-or-later

"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from logging import warning as logging_warning
from math import isnan
from typing import TYPE_CHECKING, Any

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterValueUpdateStatus
from ardupilot_methodic_configurator.plugins.backend_servo_telemetry import ServoTelemetryBackend
from ardupilot_methodic_configurator.plugins.data_model_battery_monitor import BatteryMonitorDataModel

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
    from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor

# pylint: disable=too-many-public-methods

DEFAULT_TRIM_PWM = 1500
TRIM_WARNING_DELTA_PWM = 50
SERVO_PWM_MIN = 500  # ArduPilot SERVOx_MIN/MAX/TRIM documented range
SERVO_PWM_MAX = 2200
DEFAULT_SERVO_MIN_PWM = 1100
DEFAULT_SERVO_MAX_PWM = 1900
MAX_SERVO_OUTPUTS = 32


class PlaneMode(IntEnum):
    """ArduPlane custom-mode numbers used by this plugin."""

    MANUAL = 0
    FBWA = 5
    QSTABILIZE = 17


PLANE_MODE_NAMES: dict[int, str] = {
    0: "MANUAL",
    1: "CIRCLE",
    2: "STABILIZE",
    3: "TRAINING",
    4: "ACRO",
    5: "FBWA",
    6: "FBWB",
    7: "CRUISE",
    8: "AUTOTUNE",
    10: "AUTO",
    11: "RTL",
    12: "LOITER",
    13: "TAKEOFF",
    14: "AVOID_ADSB",
    15: "GUIDED",
    17: "QSTABILIZE",
    18: "QHOVER",
    19: "QLOITER",
    20: "QLAND",
    21: "QRTL",
    22: "QAUTOTUNE",
    23: "QACRO",
    24: "THERMAL",
    25: "LOITER_ALT_QLAND",
}


class StickAxis(StrEnum):
    """Primary flight-control RC input axes and their RCMAP parameter."""

    ROLL = "RCMAP_ROLL"
    PITCH = "RCMAP_PITCH"
    YAW = "RCMAP_YAW"


_DEFAULT_RCMAP = {StickAxis.ROLL: 1, StickAxis.PITCH: 2, StickAxis.YAW: 4}

# SERVOx_FUNCTION values of primary flight-control surfaces
CONTROL_SURFACE_FUNCTIONS: dict[int, str] = {
    4: "Aileron",
    19: "Elevator",
    21: "Rudder",
    77: "Elevon Left",
    78: "Elevon Right",
    79: "V-Tail Left",
    80: "V-Tail Right",
}

# SERVOx_FUNCTION values of tilt-rotor servos
TILT_SERVO_FUNCTIONS: dict[int, str] = {
    41: "Tilt Motors Front",
    45: "Tilt Motors Rear",
    46: "Tilt Motor Rear Left",
    47: "Tilt Motor Rear Right",
    75: "Tilt Motor Front Left",
    76: "Tilt Motor Front Right",
}

# Q_TILT_TYPE values (ArduPlane tiltrotor.cpp)
Q_TILT_TYPES: dict[int, str] = {0: "Continuous", 1: "Binary", 2: "Vectored Yaw", 3: "Bicopter"}
Q_TILT_TYPE_BICOPTER = 3

TILT_SETTING_PARAMETERS = ("Q_TILT_TYPE", "Q_TILT_YAW_ANGLE", "Q_TILT_FIX_ANGLE")

# Expected surface movements, after the four-channel plane guide
AIRFRAME_MOVEMENT_CHECKS: tuple[tuple[str, str], ...] = (
    ("Pitch the nose up", "Elevator moves down (the autopilot pushes the nose back down)"),
    ("Pitch the nose down", "Elevator moves up"),
    ("Roll to the left", "Right aileron moves up, left aileron moves down"),
    ("Roll to the right", "Right aileron moves down, left aileron moves up"),
    ("Roll to the left", "Rudder moves right"),
    ("Roll to the right", "Rudder moves left"),
)

STICK_MOVEMENT_CHECKS: tuple[tuple[str, str], ...] = (
    ("Roll stick right", "Right aileron moves up, left aileron moves down"),
    ("Roll stick left", "Right aileron moves down, left aileron moves up"),
    ("Pitch stick up (pull back)", "Elevator moves up"),
    ("Pitch stick down (push forward)", "Elevator moves down"),
    ("Yaw stick right", "Rudder moves right"),
    ("Yaw stick left", "Rudder moves left"),
)


class ControlSurfaceSetupError(Exception):
    """Raised when a control surface setup operation cannot be performed."""


class EndpointKind(StrEnum):
    """Servo PWM endpoint parameter suffixes."""

    MIN = "MIN"
    TRIM = "TRIM"
    MAX = "MAX"


@dataclass(frozen=True)
class ServoChannel:
    """A servo output assigned to a function this plugin adjusts."""

    number: int
    function: int
    label: str

    def param(self, suffix: str) -> str:
        """Return the SERVOx parameter name for ``suffix`` (e.g. ``REVERSED``)."""
        return f"SERVO{self.number}_{suffix}"

    @property
    def display_name(self) -> str:
        """Short human-readable name, e.g. ``SERVO2 Aileron``."""
        return f"SERVO{self.number} {_(self.label)}"


@dataclass
class SaveResult:
    """Outcome of verifying and staging a set of parameters."""

    staged: list[str] = field(default_factory=list)
    mismatched: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True when every parameter was verified and staged."""
        return bool(self.staged) and not self.mismatched and not self.failed

    def message(self) -> str:
        """Localized summary of the outcome."""
        parts = []
        if self.staged:
            parts.append(
                _("Saved %(count)d parameter(s) to the flight controller and the current step: %(names)s")
                % {"count": len(self.staged), "names": ", ".join(self.staged)}
            )
        if self.mismatched:
            parts.append(
                _("The flight controller did not confirm: %(names)s. Check the connection and save again.")
                % {"names": ", ".join(self.mismatched)}
            )
        if self.failed:
            parts.append(
                _("Could not add to the current step: %(names)s") % {"names": ", ".join(self.failed)},
            )
        if not parts:
            return _("There are no parameters to save.")
        return "\n".join(parts)


class ControlSurfaceSetupDataModel:  # pylint: disable=too-many-instance-attributes
    """Business logic for live control surface and tilt-rotor servo setup."""

    def __init__(
        self,
        flight_controller: "FlightController",
        filesystem: "LocalFilesystem",
        parameter_editor: "ParameterEditor | None" = None,
    ) -> None:
        self.flight_controller = flight_controller
        self.filesystem = filesystem
        self.parameter_editor = parameter_editor
        self.battery_monitor = BatteryMonitorDataModel(flight_controller)
        self._telemetry = ServoTelemetryBackend(flight_controller)
        self._servo_pwm: dict[int, int] = {}
        self._current_mode: int | None = None
        self._initial_mode: int | None = None
        self._mode_changed_by_plugin = False
        self._live_values: dict[str, float] = {}

    # ------------------------------------------------------------------ parameters

    @property
    def fc_parameters(self) -> dict[str, float]:
        """Parameters downloaded from the connected flight controller."""
        return self.flight_controller.fc_parameters or {}

    def get_value(self, param_name: str, default: float | None = None) -> float | None:
        """Return the value last written by this plugin, else the FC value, else ``default``."""
        if param_name in self._live_values:
            return self._live_values[param_name]
        return self.fc_parameters.get(param_name, default)

    def _int_value(self, param_name: str, default: int) -> int:
        value = self.get_value(param_name)
        if value is None or isnan(value):
            return default
        return int(value)

    def _doc_range(self, param_name: str, default_min: float, default_max: float) -> tuple[float, float]:
        doc = getattr(self.filesystem, "doc_dict", {}).get(param_name, {})
        return float(doc.get("min", default_min)), float(doc.get("max", default_max))

    def _requires_reboot(self, param_name: str) -> bool:
        doc = getattr(self.filesystem, "doc_dict", {}).get(param_name, {})
        return bool(doc.get("RebootRequired", False))

    def write_parameter(self, param_name: str, value: float) -> None:
        """
        Write a parameter to the flight controller immediately (live adjustment).

        Raises:
            ControlSurfaceSetupError: If there is no connection or the FC rejects the request

        """
        if self.flight_controller.master is None:
            raise ControlSurfaceSetupError(_("No flight controller connection available"))
        success, error = self.flight_controller.set_param(param_name, float(value))
        if not success:
            raise ControlSurfaceSetupError(
                _("Failed to set %(param)s: %(error)s") % {"param": param_name, "error": error},
            )
        self._live_values[param_name] = float(value)

    def pending_reboot_parameters(self) -> list[str]:
        """Parameters written by this plugin that only take effect after a reboot."""
        return sorted(name for name in self._live_values if self._requires_reboot(name))

    def save_parameters(self, param_names: Iterable[str], change_reason: str) -> SaveResult:
        """
        Verify parameters on the FC and stage them in the current configuration step.

        Values not yet written by this plugin are re-sent from the FC cache so the
        flight controller and the project files end up identical.
        """
        result = SaveResult()
        for name in dict.fromkeys(param_names):
            value = self.get_value(name)
            if value is None:
                result.failed.append(name)
                continue
            if name in self._live_values:
                actual = self.flight_controller.fetch_param(name)
                if actual is None or abs(actual - value) > 0.001:
                    result.mismatched.append(name)
                    continue
            if self._stage_in_current_step(name, value, change_reason):
                result.staged.append(name)
            else:
                result.failed.append(name)
        return result

    def _stage_in_current_step(self, name: str, value: float, change_reason: str) -> bool:
        editor = self.parameter_editor
        if editor is None:
            # Standalone use: the value is already stored on the flight controller.
            return True
        try:
            if name not in editor.current_step_parameters and not editor.add_parameter_to_current_file(name):
                return False
        except Exception as error:  # pylint: disable=broad-exception-caught
            logging_warning(_("Could not add %(param)s to the current step: %(error)s"), {"param": name, "error": error})
            return False
        text_value = str(int(value)) if float(value).is_integer() else str(value)
        update = editor.update_parameter_value(name, text_value, include_range_check=False)
        if update.status not in (ParameterValueUpdateStatus.UPDATED, ParameterValueUpdateStatus.UNCHANGED):
            return False
        parameter = editor.current_step_parameters.get(name)
        if parameter is not None and not parameter.change_reason:
            parameter.set_change_reason(change_reason)
        return True

    # ------------------------------------------------------------------ channel discovery

    def _channels_with_functions(self, functions: Mapping[int, str]) -> list[ServoChannel]:
        channels = []
        for number in range(1, MAX_SERVO_OUTPUTS + 1):
            function = self.get_value(f"SERVO{number}_FUNCTION")
            if function is None or isnan(function):
                continue
            function_number = int(function)
            if function_number in functions:
                channels.append(ServoChannel(number, function_number, functions[function_number]))
        return channels

    def control_surface_channels(self) -> list[ServoChannel]:
        """Servo outputs assigned to ailerons, elevators, rudders, elevons or V-tail surfaces."""
        return self._channels_with_functions(CONTROL_SURFACE_FUNCTIONS)

    def tilt_servo_channels(self) -> list[ServoChannel]:
        """Servo outputs assigned to tilt-rotor servos."""
        return self._channels_with_functions(TILT_SERVO_FUNCTIONS)

    def is_tilt_rotor(self) -> bool:
        """True when the QuadPlane tilt-rotor support is enabled."""
        return self._int_value("Q_TILT_ENABLE", 0) == 1

    def tilt_mask(self) -> int:
        """Bitmask of motors that tilt; must be non-zero for a tilt-rotor."""
        return self._int_value("Q_TILT_MASK", 0)

    def tilt_type(self) -> int:
        """Current Q_TILT_TYPE value."""
        return self._int_value("Q_TILT_TYPE", 0)

    def tilt_type_options(self) -> dict[int, str]:
        """Q_TILT_TYPE choices, preferring the firmware metadata."""
        doc = getattr(self.filesystem, "doc_dict", {}).get("Q_TILT_TYPE", {})
        values = doc.get("values")
        if isinstance(values, Mapping) and values:
            options: dict[int, str] = {}
            for key, label in values.items():
                try:
                    options[int(float(key))] = str(label)
                except (TypeError, ValueError):
                    continue
            if options:
                return options
        return dict(Q_TILT_TYPES)

    # ------------------------------------------------------------------ safety checks

    def battery_voltage_status(self) -> tuple[bool, str]:
        """
        Check that the servos have power: battery voltage must exceed BATT_ARM_VOLT.

        Returns:
            (ok, message) where message describes the reading for display

        """
        if not self.battery_monitor.is_battery_monitoring_enabled():
            return False, _("Battery monitoring is disabled. Enable it so the servo supply voltage can be checked.")
        statuses = self.battery_monitor.get_battery_statuses()
        if not statuses or 0 not in statuses:
            return False, _("Waiting for battery voltage telemetry...")
        voltage = statuses[0][0]
        arm_voltage = self.fc_parameters.get("BATT_ARM_VOLT", 0.0)
        if isnan(voltage):
            return False, _("Battery voltage is unavailable.")
        if voltage <= arm_voltage or voltage <= 0:
            return False, _("Battery voltage %(voltage).2fV must be greater than BATT_ARM_VOLT (%(arm).2fV).") % {
                "voltage": voltage,
                "arm": arm_voltage,
            }
        return True, _("Battery voltage %(voltage).2fV (BATT_ARM_VOLT %(arm).2fV)") % {
            "voltage": voltage,
            "arm": arm_voltage,
        }

    def rudder_mix_warning(self) -> str:
        """Warn when KFF_RDDRMIX is zero, which hides the FBWA rudder-on-roll response."""
        rudder_mix = self.fc_parameters.get("KFF_RDDRMIX")
        if rudder_mix is not None and rudder_mix == 0 and any(ch.function == 21 for ch in self.control_surface_channels()):
            return _("KFF_RDDRMIX is 0, so the rudder will not respond when the plane is rolled in FBWA.")
        return ""

    # ------------------------------------------------------------------ flight mode and telemetry

    @property
    def current_mode(self) -> int | None:
        """Last flight mode reported by the FC heartbeat, if any."""
        return self._current_mode

    def current_mode_name(self) -> str:
        """Readable name of the current flight mode."""
        if self._current_mode is None:
            return _("unknown")
        return PLANE_MODE_NAMES.get(self._current_mode, str(self._current_mode))

    def set_flight_mode(self, mode: PlaneMode) -> None:
        """
        Switch the FC to ``mode``, even if it is not one of the configured FLTMODEx.

        Raises:
            ControlSurfaceSetupError: If the FC rejects the mode change

        """
        if self.flight_controller.master is None:
            raise ControlSurfaceSetupError(_("No flight controller connection available"))
        if not self._mode_changed_by_plugin:
            self._initial_mode = self._current_mode
        success, error = self.flight_controller.set_flight_mode(int(mode))
        if not success:
            raise ControlSurfaceSetupError(
                _("Could not switch to %(mode)s: %(error)s") % {"mode": mode.name, "error": error},
            )
        self._mode_changed_by_plugin = True
        self._current_mode = int(mode)

    def restore_initial_mode(self) -> None:
        """Return to the flight mode active before this plugin changed it."""
        if not self._mode_changed_by_plugin or self._initial_mode is None or self.flight_controller.master is None:
            return
        success, error = self.flight_controller.set_flight_mode(self._initial_mode)
        if not success:
            logging_warning(_("Could not restore the original flight mode: %(error)s"), {"error": error})
        self._mode_changed_by_plugin = False

    def poll_telemetry(self) -> None:
        """Read pending SERVO_OUTPUT_RAW and HEARTBEAT messages into the model."""
        if self._telemetry.sync_connection():
            self._servo_pwm.clear()
            self._current_mode = None
        for message in self._telemetry.get_servo_telemetry():
            self._handle_message(message)

    def _handle_message(self, message: Any) -> None:  # noqa: ANN401
        message_type = message.get_type()
        if message_type == "SERVO_OUTPUT_RAW":
            first_servo = 1 + 16 * int(getattr(message, "port", 0))
            for index in range(16):
                value = getattr(message, f"servo{index + 1}_raw", None)
                if isinstance(value, int) and value > 0:
                    self._servo_pwm[first_servo + index] = value
        elif message_type == "HEARTBEAT":
            self._current_mode = int(message.custom_mode)

    def servo_pwm(self, servo_number: int) -> int | None:
        """Latest PWM output of ``servo_number`` or None if not received yet."""
        return self._servo_pwm.get(servo_number)

    def stop_telemetry(self) -> None:
        """Restore the default servo output stream interval."""
        self._telemetry.stop_monitoring()
        self.battery_monitor.stop_monitoring()

    # ------------------------------------------------------------------ reversal

    def is_servo_reversed(self, channel: ServoChannel) -> bool:
        """Whether SERVOx_REVERSED is set for ``channel``."""
        return self._int_value(channel.param("REVERSED"), 0) == 1

    def set_servo_reversed(self, channel: ServoChannel, *, reversed_: bool) -> None:
        """Live-write SERVOx_REVERSED."""
        self.write_parameter(channel.param("REVERSED"), 1 if reversed_ else 0)

    def rc_channel(self, axis: StickAxis) -> int:
        """RC input channel mapped to ``axis`` by RCMAP_*."""
        return self._int_value(axis.value, _DEFAULT_RCMAP[axis])

    def is_rc_reversed(self, axis: StickAxis) -> bool:
        """Whether RCx_REVERSED is set for the channel mapped to ``axis``."""
        return self._int_value(f"RC{self.rc_channel(axis)}_REVERSED", 0) == 1

    def set_rc_reversed(self, axis: StickAxis, *, reversed_: bool) -> None:
        """Live-write RCx_REVERSED for the channel mapped to ``axis``."""
        self.write_parameter(f"RC{self.rc_channel(axis)}_REVERSED", 1 if reversed_ else 0)

    def servo_reversed_parameters(self) -> list[str]:
        """SERVOx_REVERSED names of every control surface."""
        return [channel.param("REVERSED") for channel in self.control_surface_channels()]

    def rc_reversed_parameters(self) -> list[str]:
        """RCx_REVERSED names of the roll, pitch and yaw input channels."""
        return list(dict.fromkeys(f"RC{self.rc_channel(axis)}_REVERSED" for axis in StickAxis))

    # ------------------------------------------------------------------ trim and travel

    def servo_endpoint(self, channel: ServoChannel, kind: EndpointKind) -> int:
        """Current SERVOx_MIN/TRIM/MAX value."""
        defaults = {
            EndpointKind.MIN: DEFAULT_SERVO_MIN_PWM,
            EndpointKind.TRIM: DEFAULT_TRIM_PWM,
            EndpointKind.MAX: DEFAULT_SERVO_MAX_PWM,
        }
        return self._int_value(channel.param(kind.value), defaults[kind])

    def validate_servo_endpoint(self, channel: ServoChannel, kind: EndpointKind, value: int) -> str:
        """Return a translated error if ``value`` is out of range or breaks MIN <= TRIM <= MAX, else ``""``."""
        low, high = self._doc_range(channel.param(kind.value), SERVO_PWM_MIN, SERVO_PWM_MAX)
        if not low <= value <= high:
            return _("%(param)s must be between %(min)d and %(max)d µs.") % {
                "param": channel.param(kind.value),
                "min": int(low),
                "max": int(high),
            }
        endpoints = {k: self.servo_endpoint(channel, k) for k in EndpointKind}
        endpoints[kind] = value
        if channel.function in TILT_SERVO_FUNCTIONS:
            if endpoints[EndpointKind.MIN] >= endpoints[EndpointKind.MAX]:
                return _("%(min)s must stay below %(max)s.") % {
                    "min": channel.param("MIN"),
                    "max": channel.param("MAX"),
                }
            return ""
        if not endpoints[EndpointKind.MIN] <= endpoints[EndpointKind.TRIM] <= endpoints[EndpointKind.MAX]:
            return _("%(min)s <= %(trim)s <= %(max)s must hold.") % {
                "min": channel.param("MIN"),
                "trim": channel.param("TRIM"),
                "max": channel.param("MAX"),
            }
        return ""

    def set_servo_endpoint(self, channel: ServoChannel, kind: EndpointKind, value: int) -> None:
        """
        Validate and live-write SERVOx_MIN/TRIM/MAX.

        Raises:
            ControlSurfaceSetupError: If the value is invalid or cannot be written

        """
        error = self.validate_servo_endpoint(channel, kind, value)
        if error:
            raise ControlSurfaceSetupError(error)
        self.write_parameter(channel.param(kind.value), value)

    @staticmethod
    def trim_needs_mechanical_adjustment(trim: int) -> bool:
        """True when trim is more than 50 µs from 1500 µs; adjust the linkage instead."""
        return abs(trim - DEFAULT_TRIM_PWM) > TRIM_WARNING_DELTA_PWM

    def endpoint_parameters(self, channels: Iterable[ServoChannel], kinds: Iterable[EndpointKind]) -> list[str]:
        """Names of the requested endpoint parameters of ``channels``."""
        kinds = tuple(kinds)
        return [channel.param(kind.value) for channel in channels for kind in kinds]

    # ------------------------------------------------------------------ tilt rotor

    def tilt_endpoints(self, channel: ServoChannel) -> tuple[EndpointKind, EndpointKind]:
        """
        Return the (forward-flight, hover) endpoints of a tilt servo.

        ArduPlane scales tilt outputs from 0 (vertical) to 1 (forward) over SERVOx_MIN..MAX,
        so a non-reversed servo is vertical at MIN and forward at MAX; reversal swaps them.
        Bicopter tilt servos are horizontal at MIN instead. The user can still adjust either end.
        """
        forward, hover = EndpointKind.MAX, EndpointKind.MIN
        if self.tilt_type() == Q_TILT_TYPE_BICOPTER:
            forward, hover = hover, forward
        if self.is_servo_reversed(channel):
            forward, hover = hover, forward
        return forward, hover

    def tilt_setting_value(self, param_name: str) -> float | None:
        """Current value of one of the Q_TILT_* settings."""
        return self.get_value(param_name)

    def validate_tilt_setting(self, param_name: str, value: float) -> str:
        """Return a translated range error for a Q_TILT_* setting, or ``""``."""
        defaults = {"Q_TILT_TYPE": (0, 3), "Q_TILT_YAW_ANGLE": (0, 30), "Q_TILT_FIX_ANGLE": (0, 30)}
        low, high = self._doc_range(param_name, *defaults.get(param_name, (-1e9, 1e9)))
        if not low <= value <= high:
            return _("%(param)s must be between %(min)g and %(max)g.") % {"param": param_name, "min": low, "max": high}
        return ""

    def set_tilt_setting(self, param_name: str, value: float) -> None:
        """
        Validate and live-write a Q_TILT_* setting.

        Raises:
            ControlSurfaceSetupError: If the value is invalid or cannot be written

        """
        if param_name not in TILT_SETTING_PARAMETERS:
            raise ControlSurfaceSetupError(_("%(param)s is not a tilt setting") % {"param": param_name})
        error = self.validate_tilt_setting(param_name, value)
        if error:
            raise ControlSurfaceSetupError(error)
        self.write_parameter(param_name, value)

    def tilt_setup_problem(self) -> str:
        """Describe why the tilt-rotor setup cannot start, or ``""`` when it can."""
        if not self.is_tilt_rotor():
            return _("Q_TILT_ENABLE is not 1; this is not a tilt-rotor.")
        if self.tilt_mask() <= 0:
            return _("Q_TILT_MASK must be greater than 0. Set the bits of the motors that tilt.")
        if not self.tilt_servo_channels():
            return _("No servo output is assigned to a tilt servo function (41, 45, 46, 47, 75 or 76).")
        return ""

    # ------------------------------------------------------------------ lifecycle

    def shutdown(self) -> None:
        """Restore the initial flight mode and stop telemetry streams."""
        self.restore_initial_mode()
        self.stop_telemetry()
