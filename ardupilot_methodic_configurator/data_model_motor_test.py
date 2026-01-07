"""
Data model for motor test functionality.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from enum import Enum
from logging import debug as logging_debug
from logging import error as logging_error
from logging import info as logging_info
from logging import warning as logging_warning
from math import nan
from os import path as os_path
from typing import Any, Callable, Optional, Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_json_with_schema import FilesystemJSONWithSchema
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.data_model_battery_monitor import BatteryMonitorDataModel

# pylint: disable=too-many-lines


DURATION_S_MIN = 1.0  # Minimum duration for motor tests in seconds
DURATION_S_MAX = 60.0  # Maximum duration for motor tests in seconds
THROTTLE_PCT_MIN = 1  # Minimum throttle percentage for motor tests
THROTTLE_PCT_MAX = 100  # Maximum throttle percentage for motor tests


class MotorTestError(Exception):
    """Base exception for motor test related errors."""


class FlightControllerConnectionError(MotorTestError):
    """Raised when flight controller is not connected."""


class MotorTestSafetyError(MotorTestError):
    """Raised when motor test conditions are unsafe."""


class ParameterError(MotorTestError):
    """Raised when parameter operations fail."""


class MotorTestExecutionError(MotorTestError):
    """Raised when motor test execution fails."""


class FrameConfigurationError(MotorTestError):
    """Raised when frame configuration operations fail."""


class ValidationError(MotorTestError):
    """Raised when validation of input parameters fails."""


class MotorStatusEvent(str, Enum):
    """Well-known status events published by model motor operations."""

    COMMAND_SENT = "command_sent"
    STOP_SENT = "stop_sent"


MotorStatusCallback = Callable[[int, MotorStatusEvent], None]


class MotorTestDataModel:  # pylint: disable=too-many-public-methods, too-many-instance-attributes
    """
    Data model for motor test functionality.

    This class provides business logic and abstracts backend communication for motor testing,
    including frame detection, motor counting, battery monitoring, safety validation,
    and motor command execution.
    """

    def __init__(
        self,
        flight_controller: FlightController,
        filesystem: LocalFilesystem,
    ) -> None:
        """
        Initialize the motor test data model.

        Args:
            flight_controller: Backend flight controller interface
            filesystem: Backend filesystem interface

        """
        self.flight_controller = flight_controller
        self.filesystem = filesystem

        # Initialize battery monitor for safety checks (composition)
        self.battery_monitor = BatteryMonitorDataModel(flight_controller)

        # Initialize motor data loader for motor directions and test order
        self._motor_data_loader = FilesystemJSONWithSchema(
            json_filename="AP_Motors_test.json", schema_filename="AP_Motors_test_schema.json"
        )
        self._motor_data: dict = {}

        # Initialize frame configuration with defaults
        self._frame_class: int = 0  # Default to invalid
        self._frame_type: int = 0  # Default to invalid
        self._motor_count: int = 0  # Default to invalid
        self._motor_labels: list[str] = []  # default to empty
        self._motor_numbers: list[int] = []  # default to empty
        self._test_order: list[int] = []  # default to empty
        self._motor_directions: list[str] = []  # default to empty
        self._frame_layout: dict[str, Any] = {}  # default to empty

        self._test_throttle_pct = 0.0
        self._test_duration_s = 0.0
        self._first_test_acknowledged = False

        # Cache for frame options to avoid reloading them repeatedly
        self._cached_frame_options: Optional[dict[str, dict[int, str]]] = None

        # Load motor configuration data
        self._load_motor_data()

        # Motor testing requires a connected flight controller for safety
        # We must fail early if the connection is not available
        self._update_frame_configuration()

        self._get_test_settings_from_disk()

    def _load_motor_data(self) -> None:
        """Load motor configuration data from AP_Motors_test.json file."""
        try:
            # Get the directory where this module is located (contains the JSON files)
            current_dir = os_path.dirname(__file__)
            self._motor_data = self._motor_data_loader.load_json_data(current_dir)

            # Clear frame options cache since motor data changed
            self._cached_frame_options = None

            if not self._motor_data:
                logging_error(_("Failed to load motor test data from AP_Motors_test.json"))
            else:
                logging_debug(
                    _("Successfully loaded motor test data with %(layouts)d layouts"),
                    {"layouts": len(self._motor_data.get("layouts", []))},
                )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Error loading motor test data: %(error)s"), {"error": str(e)})
            self._motor_data = {}

    def _configure_frame_layout(self, frame_class: int, frame_type: int) -> None:
        """
        Configure frame layout based on frame class and type.

        This is the pure logic function that processes frame configuration
        without flight controller interaction, making it easily testable.

        Args:
            frame_class: Frame class (e.g., 1 for QUAD)
            frame_type: Frame type (e.g., 0 for PLUS, 1 for X)

        Raises:
            RuntimeError: If no motor configuration found for the frame

        """
        # Check if frame configuration has changed
        if self._frame_class == frame_class and self._frame_type == frame_type:
            return

        # Update frame parameters
        self._frame_class = frame_class
        self._frame_type = frame_type
        self._motor_count = 0
        self._frame_layout = {}

        # Find matching layout in motor data and populate motor arrays
        if self._motor_data_loader.data and "layouts" in self._motor_data_loader.data:
            for layout in self._motor_data_loader.data["layouts"]:
                if layout["Class"] == self._frame_class and layout["Type"] == self._frame_type and "motors" in layout:
                    self._frame_layout = layout
                    self._motor_count = len(layout["motors"])
                    # Generate motor labels: A-Z for first 26, then AA, AB, AC... for motors 27-32
                    self._motor_labels = []
                    for i in range(self._motor_count):
                        if i < 26:
                            self._motor_labels.append(chr(ord("A") + i))
                        else:
                            # For motors 27-32: AA, AB, AC, AD, AE, AF
                            self._motor_labels.append("A" + chr(ord("A") + (i - 26)))
                    self._motor_numbers = [0] * self._motor_count
                    self._test_order = [0] * self._motor_count
                    self._motor_directions = [""] * self._motor_count
                    for i, motor in enumerate(self._frame_layout.get("motors", [])):
                        test_order = motor.get("TestOrder")
                        if test_order and 1 <= test_order <= self._motor_count:
                            self._motor_numbers[test_order - 1] = motor.get("Number")
                            self._motor_directions[test_order - 1] = motor.get("Rotation")
                            self._test_order[i] = test_order
                    break

        if self._motor_count == 0:
            raise RuntimeError(
                _("No motor configuration found for frame class %(class)d and type %(type)d")
                % {"class": self._frame_class, "type": self._frame_type}
            )

        logging_debug(
            _("Frame configuration updated: Class=%(class)d, Type=%(type)d, Motors=%(motors)d"),
            {
                "class": self._frame_class,
                "type": self._frame_type,
                "motors": self._motor_count,
            },
        )

    def _get_test_settings_from_disk(self) -> None:
        """Load test settings from disk."""
        self._test_throttle_pct = self._get_test_throttle_pct()
        self._test_duration_s = self._get_test_duration_s()

    def _update_frame_configuration(self) -> None:
        """Update frame configuration from flight controller."""
        if self.flight_controller.master is None or not self.flight_controller.fc_parameters:
            msg = _("Flight controller connection required for motor testing")
            logging_error(msg)
            raise RuntimeError(msg)

        try:
            # Get frame info from flight controller
            frame_class, frame_type = self.flight_controller.get_frame_info()

            # Configure frame layout using the separated logic
            self._configure_frame_layout(frame_class, frame_type)

        except Exception as e:
            logging_error(_("Failed to update frame configuration: %(error)s"), {"error": str(e)})
            raise

    def refresh_from_flight_controller(self) -> bool:
        """
        Refresh frame configuration from flight controller.

        Returns:
            bool: True if successful, False if connection not ready

        """
        try:
            self._update_frame_configuration()
            return True
        except RuntimeError:
            return False

    @property
    def frame_class(self) -> int:
        """Get the current frame class."""
        return self._frame_class

    @property
    def frame_type(self) -> int:
        """Get the current frame type."""
        return self._frame_type

    @property
    def motor_count(self) -> int:
        """Get the number of motors for the current frame configuration."""
        return self._motor_count

    @property
    def motor_labels(self) -> list[str]:
        """Get motor labels (A, B, C, D, etc.) based on motor count."""
        return self._motor_labels

    @property
    def motor_numbers(self) -> list[int]:
        """Get motor numbers in test order (1, 4, 3, 2, etc.)."""
        return self._motor_numbers

    def test_order(self, motor_number: int) -> int:
        """Get the test order for a specific motor."""
        if 1 <= motor_number <= self._motor_count:
            return self._test_order[motor_number - 1] - 1
        raise ValueError(_("Invalid motor number: %(number)d") % {"number": motor_number})

    @property
    def motor_directions(self) -> list[str]:
        """Get expected motor rotation directions based on frame configuration."""
        return self._motor_directions

    def is_battery_monitoring_enabled(self) -> bool:
        """
        Check if battery monitoring is enabled in the flight controller parameters.

        Returns:
            bool: True if battery monitoring is enabled, False otherwise.

        """
        return self.battery_monitor.is_battery_monitoring_enabled()

    def get_battery_status(self) -> Optional[tuple[float, float]]:
        """
        Get the current battery voltage and current.

        Returns:
            Optional[tuple[float, float]]: (voltage, current) in volts and amps,
                                         or None if not available

        """
        return self.battery_monitor.get_battery_status()

    def get_voltage_thresholds(self) -> tuple[float, float]:
        """
        Get battery voltage thresholds for motor testing safety.

        Returns:
            tuple[float, float]: (min_voltage, max_voltage) for safe motor testing

        """
        return self.battery_monitor.get_voltage_thresholds()

    def get_voltage_status(self) -> str:
        """
        Get the battery voltage status as a string.

        Returns:
            str: "safe", "unsafe", "disabled", or "unavailable"

        """
        return self.battery_monitor.get_voltage_status()

    def is_motor_test_safe(self) -> None:
        """
        Check if motor testing is currently safe.

        Raises:
            FlightControllerConnectionError: If flight controller is not connected
            MotorTestSafetyError: If motor test conditions are unsafe

        """
        # Check if flight controller is connected
        if self.flight_controller.master is None:
            raise FlightControllerConnectionError(_("Flight controller not connected."))

        # Check battery monitoring using battery monitor
        if not self.battery_monitor.is_battery_monitoring_enabled():
            # If battery monitoring is disabled, we still warn but don't fail
            logging_warning(_("Battery monitoring disabled, cannot verify voltage."))
            return

        # Check battery voltage status using battery monitor
        voltage_status = self.battery_monitor.get_voltage_status()
        if voltage_status == "unavailable":
            raise MotorTestSafetyError(_("Could not read battery status."))
        if voltage_status == "critical":
            battery_status = self.battery_monitor.get_battery_status()
            voltage, _current = battery_status if battery_status else (nan, nan)
            min_voltage, max_voltage = self.battery_monitor.get_voltage_thresholds()
            raise MotorTestSafetyError(
                _("Battery voltage %(voltage).1fV is outside safe range (%(min).1fV - %(max).1fV)")
                % {
                    "voltage": voltage,
                    "min": min_voltage,
                    "max": max_voltage,
                }
            )

    def set_parameter(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        param_name: str,
        value: float,
        reset_progress_callback: Union[None, Callable[[int, int], None]] = None,
        connection_progress_callback: Union[None, Callable[[int, int], None]] = None,
        extra_sleep_time: Optional[int] = 0,
    ) -> None:
        """
        Set a parameter value and upload to flight controller.

        Args:
            param_name: Parameter name (e.g., "MOT_SPIN_ARM")
            value: Parameter value
            reset_progress_callback: Optional callback for reset progress updates
            connection_progress_callback: Optional callback for connection progress updates
            extra_sleep_time: Optional additional sleep time before re-connecting

        Raises:
            FlightControllerConnectionError: If flight controller is not connected
            ValidationError: If parameter value is invalid
            ParameterError: If parameter setting fails
            TimeoutError: If parameter setting times out

        """
        if self.flight_controller.master is None:
            raise FlightControllerConnectionError(_("No flight controller connection available"))

        try:
            # Validate parameter bounds if possible
            if param_name in ["MOT_SPIN_ARM", "MOT_SPIN_MIN"] and not 0.0 <= value <= 1.0:
                raise ValidationError(
                    _("%(param)s value %(value).3f is outside valid range (0.0 - 1.0)")
                    % {
                        "param": param_name,
                        "value": value,
                    }
                )

            requires_reset = False
            if param_name in self.filesystem.doc_dict:
                min_value = self.filesystem.doc_dict[param_name].get("min", -float("inf"))
                max_value = self.filesystem.doc_dict[param_name].get("max", float("inf"))
                requires_reset = self.filesystem.doc_dict[param_name].get("RebootRequired", False)
                if value < min_value:
                    raise ValidationError(
                        _("%(param)s value %(value).3f is smaller than %(min)f")
                        % {"param": param_name, "value": value, "min": min_value}
                    )
                if value > max_value:
                    raise ValidationError(
                        _("%(param)s value %(value).3f is greater than %(max)f")
                        % {"param": param_name, "value": value, "max": max_value}
                    )

            # Set parameter and verify it was set correctly
            success, error_msg = self.flight_controller.set_param(param_name, value)
            if not success:
                raise ParameterError(
                    _("Failed to set parameter %(param)s: %(error)s") % {"param": param_name, "error": error_msg}
                )
            # Read back the parameter to verify it was set correctly
            actual_value = self.flight_controller.fetch_param(param_name)
            if actual_value is not None and abs(actual_value - value) < 0.001:  # Allow small floating-point tolerance
                logging_info(_("Parameter %(param)s set to %(value).3f"), {"param": param_name, "value": value})
                if requires_reset:
                    self.flight_controller.reset_and_reconnect(
                        reset_progress_callback, connection_progress_callback, extra_sleep_time
                    )
                return
            raise ParameterError(
                _("Parameter %(param)s verification failed: expected %(expected).3f, got %(actual)s")
                % {
                    "param": param_name,
                    "expected": value,
                    "actual": actual_value if actual_value is not None else "None",
                }
            )

        except (ValidationError, ParameterError, TimeoutError):
            raise
        except Exception as e:
            error_msg = _("Error setting parameter %(param)s: %(error)s") % {
                "param": param_name,
                "error": str(e),
            }
            logging_error(error_msg)
            raise ParameterError(error_msg) from e

    def get_parameter(self, param_name: str) -> Optional[float]:
        """
        Get a parameter value from the flight controller.

        Args:
            param_name: Parameter name

        Returns:
            Optional[float]: Parameter value or None if not available

        """
        if self.flight_controller.master is None or not self.flight_controller.fc_parameters:
            return None

        return self.flight_controller.fc_parameters.get(param_name)

    def set_motor_spin_arm_value(
        self,
        value: float,
        reset_progress_callback: Union[None, Callable[[int, int], None]] = None,
        connection_progress_callback: Union[None, Callable[[int, int], None]] = None,
    ) -> None:
        """Set MOT_SPIN_ARM ensuring a 0.02 margin relative to MOT_SPIN_MIN."""
        spin_min = self.get_parameter("MOT_SPIN_MIN")
        if spin_min is not None and value > spin_min - 0.02:
            raise ValidationError(
                _("MOT_SPIN_ARM must stay at least 0.02 below MOT_SPIN_MIN (current %(min).2f).") % {"min": spin_min}
            )

        self.set_parameter("MOT_SPIN_ARM", value, reset_progress_callback, connection_progress_callback)

    def set_motor_spin_min_value(self, value: float) -> None:
        """Set MOT_SPIN_MIN ensuring it keeps 0.02 margin above MOT_SPIN_ARM."""
        spin_arm = self.get_parameter("MOT_SPIN_ARM")
        if spin_arm is None:
            raise ParameterError(_("MOT_SPIN_ARM must be available before updating MOT_SPIN_MIN."))
        if value < spin_arm + 0.02:
            raise ValidationError(
                _("MOT_SPIN_MIN must be at least 0.02 higher than MOT_SPIN_ARM (current %(arm).2f).") % {"arm": spin_arm}
            )

        self.set_parameter("MOT_SPIN_MIN", value)

    def test_motor(self, test_sequence_nr: int, motor_output_nr: int, throttle_percent: int, timeout_seconds: int) -> None:
        """
        Test a specific motor.

        Args:
            test_sequence_nr: Test sequence number (0-based)
            motor_output_nr: Motor output number (1-based, as used by ArduPilot)
            throttle_percent: Throttle percentage (1-100)
            timeout_seconds: Test duration in seconds

        Raises:
            FlightControllerConnectionError: If flight controller is not connected
            MotorTestSafetyError: If motor test conditions are unsafe
            ValidationError: If motor number or throttle percentage is invalid
            MotorTestExecutionError: If motor test execution fails

        """
        # Safety check
        self.is_motor_test_safe()

        # Validate test sequence number
        if not 0 <= test_sequence_nr <= self._motor_count - 1:
            raise ValidationError(
                _("Invalid test sequence number %(number)d (valid range: 0-%(max)d)")
                % {
                    "number": test_sequence_nr,
                    "max": self._motor_count - 1,
                }
            )

        # Validate motor output number
        if not 1 <= motor_output_nr <= self._motor_count:
            raise ValidationError(
                _("Invalid motor output number %(number)d (valid range: 1-%(max)d)")
                % {
                    "number": motor_output_nr,
                    "max": self._motor_count,
                }
            )

        # Validate motor output number
        if self.motor_numbers[test_sequence_nr] != motor_output_nr:
            raise ValidationError(
                _("Invalid motor output number %(number)d (expected: %(expected)d)")
                % {
                    "number": motor_output_nr,
                    "expected": self.motor_numbers[test_sequence_nr],
                }
            )

        # Validate throttle percentage
        if not THROTTLE_PCT_MIN <= throttle_percent <= THROTTLE_PCT_MAX:
            raise ValidationError(
                _("Invalid throttle percentage %(throttle)d (valid range: %(min)d-%(max)d)")
                % {
                    "throttle": throttle_percent,
                    "min": THROTTLE_PCT_MIN,
                    "max": THROTTLE_PCT_MAX,
                }
            )

        # Validate test duration
        if timeout_seconds < DURATION_S_MIN:
            raise ValidationError(
                _("Invalid test duration %(duration)d (valid range: %(min)d-%(max)d)")
                % {"duration": timeout_seconds, "min": DURATION_S_MIN, "max": DURATION_S_MAX}
            )
        if timeout_seconds > DURATION_S_MAX:
            raise ValidationError(
                _("Invalid test duration %(duration)d (valid range: %(min)d-%(max)d)")
                % {"duration": timeout_seconds, "min": DURATION_S_MIN, "max": DURATION_S_MAX}
            )

        # Execute motor test
        success, message = self.flight_controller.test_motor(
            test_sequence_nr, self.motor_labels[test_sequence_nr], motor_output_nr, throttle_percent, timeout_seconds
        )
        if not success:
            raise MotorTestExecutionError(message)

    def _emit_status_event(
        self,
        callback: Optional[MotorStatusCallback],
        motor_number: int,
        event: MotorStatusEvent,
    ) -> None:
        """Notify listeners about a status change."""
        if callback is not None:
            callback(motor_number, event)

    def run_single_motor_test(
        self,
        test_sequence_nr: int,
        motor_output_nr: int,
        status_callback: Optional[MotorStatusCallback] = None,
    ) -> None:
        """Execute a single motor test using stored throttle/duration settings."""
        throttle_pct = self.get_test_throttle_pct()
        duration = int(self.get_test_duration_s())
        self.test_motor(test_sequence_nr, motor_output_nr, throttle_pct, duration)
        self._emit_status_event(status_callback, motor_output_nr, MotorStatusEvent.COMMAND_SENT)

    def test_all_motors(self, throttle_percent: int, timeout_seconds: int) -> None:
        """
        Test all motors simultaneously.

        Args:
            throttle_percent: Throttle percentage (1-100)
            timeout_seconds: Test duration in seconds

        Raises:
            FlightControllerConnectionError: If flight controller is not connected
            MotorTestSafetyError: If motor test conditions are unsafe
            MotorTestExecutionError: If motor test execution fails

        """
        # Safety check
        self.is_motor_test_safe()

        # Execute all motors test
        success, message = self.flight_controller.test_all_motors(self.motor_count, throttle_percent, timeout_seconds)
        if not success:
            raise MotorTestExecutionError(message)

    def test_motors_in_sequence(self, throttle_percent: int, timeout_seconds: int) -> None:
        """
        Test motors in sequence (A, B, C, D, etc.).

        Args:
            throttle_percent: Throttle percentage (0-100)
            timeout_seconds: Test duration per motor in seconds

        Raises:
            FlightControllerConnectionError: If flight controller is not connected
            MotorTestSafetyError: If motor test conditions are unsafe
            MotorTestExecutionError: If motor test execution fails

        """
        # Safety check
        self.is_motor_test_safe()

        # Execute sequential test starting from motor 1
        success, message = self.flight_controller.test_motors_in_sequence(
            1, self.motor_count, throttle_percent, timeout_seconds
        )
        if not success:
            raise MotorTestExecutionError(message)

    def run_all_motors_test(self, status_callback: Optional[MotorStatusCallback] = None) -> None:
        """Execute an all-motors test using stored settings and report events."""
        throttle_pct = self.get_test_throttle_pct()
        duration = int(self.get_test_duration_s())
        self.test_all_motors(throttle_pct, duration)
        for motor_number in range(1, self.motor_count + 1):
            self._emit_status_event(status_callback, motor_number, MotorStatusEvent.COMMAND_SENT)

    def run_sequential_motor_test(self, status_callback: Optional[MotorStatusCallback] = None) -> None:
        """Execute a sequential test using stored settings and report events."""
        throttle_pct = self.get_test_throttle_pct()
        duration = int(self.get_test_duration_s())
        self.test_motors_in_sequence(throttle_pct, duration)
        for motor_number in range(1, self.motor_count + 1):
            self._emit_status_event(status_callback, motor_number, MotorStatusEvent.COMMAND_SENT)

    def stop_all_motors(self) -> None:
        """
        Emergency stop for all motors.

        Raises:
            MotorTestExecutionError: If emergency stop fails

        """
        success, message = self.flight_controller.stop_all_motors()
        if not success:
            raise MotorTestExecutionError(message)

    def emergency_stop_motors(self, status_callback: Optional[MotorStatusCallback] = None) -> None:
        """Stop motors and emit status events for listeners."""
        self.stop_all_motors()
        for motor_number in range(1, self.motor_count + 1):
            self._emit_status_event(status_callback, motor_number, MotorStatusEvent.STOP_SENT)

    def get_motor_diagram_path(self) -> tuple[str, str]:
        """
        Get the filepath for the motor diagram SVG file for the current frame.

        Returns:
            tuple[str, str]: (absolute_path, error_message) - Absolute path to the motor diagram SVG file,
                             or empty string if not available

        """
        return ProgramSettings.motor_diagram_filepath(self._frame_class, self._frame_type)

    def motor_diagram_exists(self) -> bool:
        """
        Check if a motor diagram exists for the current frame configuration.

        Returns:
            bool: True if diagram exists, False otherwise

        """
        return ProgramSettings.motor_diagram_exists(self._frame_class, self._frame_type)

    def _get_test_duration_s(self) -> float:
        """
        Get the current motor test duration setting from disk.

        Returns:
            float: Test duration in seconds

        """
        try:
            duration = ProgramSettings.get_setting("motor_test/duration")
            if duration is None:
                raise ReferenceError(_("Motor test duration setting not found"))
            duration = float(duration)
            if duration < DURATION_S_MIN:
                raise ValueError(_("Motor test duration must be at least %(min)d second") % {"min": DURATION_S_MIN})
            if duration > DURATION_S_MAX:
                raise ValueError(_("Motor test duration must not exceed %(max)d seconds") % {"max": DURATION_S_MAX})
            return duration
        except (ReferenceError, ValueError) as exc:
            logging_error(_("Invalid motor test duration setting: %(error)s"), {"error": str(exc)})
            raise exc

    def get_test_duration_s(self) -> float:
        """
        Get the current motor test duration setting.

        Returns:
            float: Test duration in seconds

        """
        return self._test_duration_s

    def set_test_duration_s(self, duration: float) -> None:
        """
        Set the motor test duration setting.

        Args:
            duration: Test duration in seconds

        """
        try:
            if duration < DURATION_S_MIN:
                raise ValueError(_("Motor test duration must be at least %(min)d second") % {"min": DURATION_S_MIN})
            if duration > DURATION_S_MAX:
                raise ValueError(_("Motor test duration must not exceed %(max)d seconds") % {"max": DURATION_S_MAX})
            ProgramSettings.set_setting("motor_test/duration", duration)
            self._test_duration_s = int(duration)
        except ValueError as exc:
            logging_error(_("Invalid motor test duration setting: %(error)s"), {"error": str(exc)})
            raise exc
        except Exception as exc:
            logging_error(_("Failed to save duration setting: %(error)s"), {"error": str(exc)})
            raise exc

    def _get_test_throttle_pct(self) -> int:
        """
        Get the current motor test throttle percentage setting from disk.

        Returns:
            int: Throttle percentage (1-100)

        """
        try:
            throttle_pct = ProgramSettings.get_setting("motor_test/throttle_pct")
            if throttle_pct is None:
                raise ReferenceError(_("Motor test throttle percentage setting not found"))
            throttle_pct = int(throttle_pct)
            if throttle_pct < THROTTLE_PCT_MIN:
                raise ValueError(_("Motor test throttle percentage must be at least %(min)d%%") % {"min": THROTTLE_PCT_MIN})
            if throttle_pct > THROTTLE_PCT_MAX:
                raise ValueError(_("Motor test throttle percentage must not exceed %(max)d%%") % {"max": THROTTLE_PCT_MAX})
            return throttle_pct
        except (ReferenceError, ValueError) as exc:
            logging_error(_("Invalid motor test throttle percentage setting: %(error)s"), {"error": str(exc)})
            raise exc

    def get_test_throttle_pct(self) -> int:
        """
        Get the current motor test throttle percentage setting.

        Returns:
            int: Throttle percentage (1-100)

        """
        return int(self._test_throttle_pct)

    def set_test_throttle_pct(self, throttle_pct: int) -> None:
        """
        Set the motor test throttle percentage setting.

        Args:
            throttle_pct: Throttle percentage (1-100)

        """
        try:
            if throttle_pct < THROTTLE_PCT_MIN:
                raise ValueError(_("Motor test throttle percentage must be at least %(min)d%%") % {"min": THROTTLE_PCT_MIN})
            if throttle_pct > THROTTLE_PCT_MAX:
                raise ValueError(_("Motor test throttle percentage must not exceed %(max)d%%") % {"max": THROTTLE_PCT_MAX})
            ProgramSettings.set_setting("motor_test/throttle_pct", throttle_pct)
            self._test_throttle_pct = throttle_pct
        except ValueError as exc:
            logging_error(_("Invalid motor test throttle percentage setting: %(error)s"), {"error": str(exc)})
            raise exc
        except Exception as exc:
            logging_error(_("Failed to save throttle percentage setting: %(error)s"), {"error": str(exc)})
            raise exc

    def update_frame_configuration(self, frame_class: int, frame_type: int) -> None:
        """
        Update the frame configuration and upload to flight controller.

        Args:
            frame_class: New frame class
            frame_type: New frame type

        Raises:
            FlightControllerConnectionError: If flight controller is not connected
            ParameterError: If parameter setting fails
            FrameConfigurationError: If frame configuration update fails

        """
        if self.flight_controller.master is None or not self.flight_controller.fc_parameters:
            raise FlightControllerConnectionError(_("Flight controller connection required for frame configuration update"))

        try:
            # Only set FRAME_CLASS parameter if it has changed
            if self._frame_class != frame_class:
                self.set_parameter("FRAME_CLASS", float(frame_class))

            # Only set FRAME_TYPE parameter if it has changed
            if self._frame_type != frame_type:
                self.set_parameter("FRAME_TYPE", float(frame_type))

            # Update internal state
            self._frame_class = frame_class
            self._frame_type = frame_type

            # Recalculate motor count using motor data loader
            self._motor_count = 0
            if self._motor_data_loader.data and "layouts" in self._motor_data_loader.data:
                # Find a layout that matches the current frame class and type
                for layout in self._motor_data_loader.data["layouts"]:
                    if layout.get("Class") == frame_class and layout.get("Type") == frame_type and "motors" in layout:
                        self._frame_layout = layout
                        self._motor_count = len(layout["motors"])
                        break

            logging_info(
                _("Frame configuration updated: Class=%(class)d, Type=%(type)d, Motors=%(motors)d"),
                {
                    "class": self._frame_class,
                    "type": self._frame_type,
                    "motors": self._motor_count,
                },
            )

        except (FlightControllerConnectionError, ParameterError):
            raise
        except Exception as e:
            error_msg = _("Failed to update frame configuration: %(error)s") % {"error": str(e)}
            logging_error(error_msg)
            raise FrameConfigurationError(error_msg) from e

    def get_current_frame_class_types(self) -> dict[int, str]:
        """
        Get frame types available for the current frame class only.

        Returns:
            dict[int, str]: Dictionary of frame type codes to names for current frame class

        """
        if self.flight_controller.master is None or not self.flight_controller.fc_parameters:
            logging_warning(_("Flight controller connection required for current frame class"))
            return {}

        # Get current frame class from flight controller
        current_frame_class = self.flight_controller.fc_parameters.get("FRAME_CLASS")
        if current_frame_class is None:
            logging_warning(_("FRAME_CLASS parameter not found in flight controller"))
            return {}

        frame_class_int = int(current_frame_class)

        # Get all frame options
        all_frame_options = self.get_frame_options()

        # Build a mapping from frame class number to class name using the JSON data
        class_number_to_name = {}
        if self._motor_data_loader.data and "layouts" in self._motor_data_loader.data:
            for layout in self._motor_data_loader.data["layouts"]:
                class_num = layout.get("Class")
                class_name = layout.get("ClassName")
                if class_num is not None and class_name is not None:
                    class_number_to_name[class_num] = class_name

        # Find the class name for the current frame class number
        if frame_class_int in class_number_to_name:
            current_class_name = class_number_to_name[frame_class_int]
            types_for_class = all_frame_options.get(current_class_name, {})
            logging_debug(
                _("Found %(count)d frame types for current frame class %(class)d (%(name)s)"),
                {
                    "count": len(types_for_class),
                    "class": frame_class_int,
                    "name": current_class_name,
                },
            )
            return types_for_class

        # Class number not found in motor data
        max_class = max(class_number_to_name.keys()) if class_number_to_name else 0
        logging_warning(
            _("Current frame class %(class)d is not defined in motor configuration (max defined: %(max)d)"),
            {"class": frame_class_int, "max": max_class},
        )
        return {}

    def get_frame_options(self) -> dict[str, dict[int, str]]:  # pylint: disable=too-many-branches
        """
        Get all available frame configuration options.

        Uses motor data loader as the primary source, falling back to doc_dict if necessary.
        Results are cached to avoid repeated processing.

        Returns:
            dict[str, dict[int, str]]: A dictionary of frame options grouped by class name.

        """
        # Return cached result if available
        if self._cached_frame_options is not None:
            logging_debug(
                _("Returning cached frame options with %(count)d classes"), {"count": len(self._cached_frame_options)}
            )
            return self._cached_frame_options

        frame_options: dict[str, dict[int, str]] = {}

        # Primary source: Use motor data loader - same logic as _update_frame_configuration
        if self._motor_data_loader.data and "layouts" in self._motor_data_loader.data:
            layouts = self._motor_data_loader.data["layouts"]
            logging_debug(
                _("Loading frame options from motor data loader (%(count)d layouts available)"), {"count": len(layouts)}
            )

            for layout in layouts:
                # Use dictionary get() method to avoid exceptions
                frame_type = layout.get("Type")
                class_name = layout.get("ClassName")
                type_name = layout.get("TypeName")

                # Skip if required fields are missing
                if frame_type is None or class_name is None or type_name is None:
                    logging_warning(_("Skipping motor layout with missing required fields"))
                    continue

                # Initialize class group if not exists
                if class_name not in frame_options:
                    frame_options[class_name] = {}

                # Add this frame type to the class
                frame_options[class_name][frame_type] = type_name

            if frame_options:
                logging_debug(
                    _("Successfully loaded %(count)d frame classes from motor data loader"), {"count": len(frame_options)}
                )

        # Fallback: Use doc_dict only if motor data loader didn't provide data
        if not frame_options and hasattr(self.filesystem, "doc_dict") and self.filesystem.doc_dict:  # pylint: disable=too-many-nested-blocks
            logging_debug(_("Motor data unavailable, using doc_dict as fallback for frame options"))

            # Get FRAME_TYPE options (these contain both class and type info)
            if "FRAME_TYPE" in self.filesystem.doc_dict:
                frame_type_values = self.filesystem.doc_dict["FRAME_TYPE"].get("values", {})

                # Group frame types by their corresponding frame class
                for code, name in frame_type_values.items():
                    if code is not None:
                        try:
                            type_code = int(code)
                            # Extract frame class from the name (e.g., "Quad: X" -> "QUAD")
                            if ":" in name:
                                class_name, type_name = name.split(":", 1)
                                class_name = class_name.strip().upper()
                                type_name = type_name.strip()

                                if class_name not in frame_options:
                                    frame_options[class_name] = {}
                                frame_options[class_name][type_code] = type_name
                        except (ValueError, TypeError):
                            continue

            if frame_options:
                logging_debug(
                    _("Successfully loaded %(count)d frame classes from parameter metadata fallback"),
                    {"count": len(frame_options)},
                )

        # Log the final result
        if frame_options:
            total_types = sum(len(types) for types in frame_options.values())
            logging_debug(
                _("Frame options loaded: %(count)d classes with %(types)d total types"),
                {
                    "count": len(frame_options),
                    "types": total_types,
                },
            )
        else:
            logging_warning(_("No frame options could be loaded from motor data or parameter metadata"))

        # Cache the result for future calls
        self._cached_frame_options = frame_options

        return frame_options

    def refresh_connection_status(self) -> bool:
        """
        Refresh the connection status and update frame configuration if needed.

        Returns:
            bool: True if connected to flight controller, False otherwise

        """
        if self.flight_controller.master is None:
            return False

        try:
            # Re-read frame configuration from flight controller
            self._update_frame_configuration()
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_warning(_("Failed to refresh frame configuration: %(error)s"), {"error": str(e)})
            return False

    def parse_frame_type_selection(self, selected_text: str) -> tuple[int, int]:
        """
        Parse frame type selection text and return frame codes.

        Args:
            selected_text: Selected text with frame type name (frame class is current FRAME_CLASS parameter)

        Returns:
            tuple[int, int]: (frame_class_code, frame_type_code)

        Raises:
            ValidationError: If frame type selection text is invalid or frame configuration not found

        """
        if self.flight_controller.master is None or not self.flight_controller.fc_parameters:
            raise ValidationError(_("Flight controller connection required for frame type parsing"))

        # Get current frame class from flight controller
        current_frame_class = self.flight_controller.fc_parameters.get("FRAME_CLASS")
        if current_frame_class is None:
            raise ValidationError(_("FRAME_CLASS parameter not found in flight controller"))

        try:
            frame_class_code = int(current_frame_class)
            frame_type_name = selected_text.strip()

            # Get frame types for current frame class
            current_types = self.get_current_frame_class_types()

            # Find frame type code by name
            frame_type_code = None
            for type_code, type_name in current_types.items():
                if type_name.upper() == frame_type_name.upper():
                    frame_type_code = type_code
                    break

            if frame_type_code is None:
                raise ValidationError(
                    _("Could not find frame type '%(text)s' in current frame class") % {"text": selected_text}
                )

            return frame_class_code, frame_type_code

        except (ValueError, TypeError) as e:
            raise ValidationError(_("Error parsing frame type: %(error)s") % {"error": str(e)}) from e

    def update_frame_type_from_selection(
        self,
        selected_text: str,
        reset_progress_callback: Union[None, Callable[[int, int], None]] = None,
        connection_progress_callback: Union[None, Callable[[int, int], None]] = None,
        extra_sleep_time: Optional[int] = None,
    ) -> bool:
        """
        Update frame configuration based on user selection.

        Args:
            selected_text: Selected text in format "Frame Class: Frame Type"
            reset_progress_callback: Callback for resetting progress
            connection_progress_callback: Callback for connection progress
            extra_sleep_time: Additional sleep time before setting parameters

        Returns:
            bool: True if successful

        Raises:
            ValidationError: If frame type selection text is invalid
            ParameterError: If parameter setting fails
            FrameConfigurationError: If frame configuration update fails

        """
        try:
            frame_class_code, frame_type_code = self.parse_frame_type_selection(selected_text)

            # Immediately upload parameters to flight controller
            if self.frame_class != frame_class_code:
                self.set_parameter(
                    "FRAME_CLASS", frame_class_code, reset_progress_callback, connection_progress_callback, extra_sleep_time
                )
            if self.frame_type != frame_type_code:
                self.set_parameter(
                    "FRAME_TYPE", frame_type_code, reset_progress_callback, connection_progress_callback, extra_sleep_time
                )

            logging_info(
                _("Updated frame configuration: FRAME_CLASS=%(class)d, FRAME_TYPE=%(type)d"),
                {"class": frame_class_code, "type": frame_type_code},
            )

            # Update internal state and recalculate motor count
            self._frame_class = frame_class_code
            self._frame_type = frame_type_code
            self._motor_count = 0
            if self._motor_data_loader.data and "layouts" in self._motor_data_loader.data:
                # Find a layout that matches the current frame class and type
                for layout in self._motor_data_loader.data["layouts"]:
                    if (
                        layout.get("Class") == frame_class_code
                        and layout.get("Type") == frame_type_code
                        and "motors" in layout
                    ):
                        self._frame_layout = layout
                        self._motor_count = len(layout["motors"])
                        break

            return True

        except (ParameterError, ValidationError):
            raise
        except Exception as e:
            error_msg = _("Failed to update frame configuration: %(error)s") % {"error": str(e)}
            logging_error(error_msg)
            raise FrameConfigurationError(error_msg) from e

    def update_frame_type_by_key(
        self,
        selected_key: str,
        reset_progress_callback: Union[None, Callable[[int, int], None]] = None,
        connection_progress_callback: Union[None, Callable[[int, int], None]] = None,
        extra_sleep_time: Optional[int] = None,
    ) -> bool:
        """Update frame configuration using the combobox key directly."""
        try:
            frame_type_code = int(selected_key)
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Invalid frame type selection")) from exc

        current_types = self.get_current_frame_class_types()
        frame_type_name = current_types.get(frame_type_code)
        if frame_type_name is None:
            raise ValidationError(_("Frame type %(key)s is not available for current frame class") % {"key": selected_key})

        return self.update_frame_type_from_selection(
            frame_type_name,
            reset_progress_callback,
            connection_progress_callback,
            extra_sleep_time,
        )

    def get_battery_status_color(self) -> str:
        """
        Get the appropriate color for battery voltage display.

        Returns:
            str: Color name ("green", "orange", "red", "gray")

        """
        voltage_status = self.get_voltage_status()
        if voltage_status == "safe":
            return "green"
        if voltage_status == "low":
            return "orange"
        if voltage_status == "critical":
            return "red"
        return "gray"

    def get_battery_display_text(self) -> tuple[str, str]:
        """
        Get formatted battery status text for display.

        Returns:
            tuple[str, str]: (voltage_text, current_text)

        """
        if not self.is_battery_monitoring_enabled():
            return _("Voltage: Disabled"), _("Current: Disabled")

        status = self.get_battery_status()
        if status:
            voltage, current = status
            voltage_text = _("Voltage: %(volt).2fV") % {"volt": voltage}
            current_text = _("Current: %(curr).2fA") % {"curr": current}
            return voltage_text, current_text
        return _("Voltage: N/A"), _("Current: N/A")

    def should_show_first_test_warning(self) -> bool:
        """Return True when first-time warning still needs acknowledgement."""
        return not self._first_test_acknowledged

    def acknowledge_first_test_warning(self) -> None:
        """Record that the user has accepted the first-time warning."""
        self._first_test_acknowledged = True

    def get_safety_warning_message(self) -> str:
        """
        Get the safety warning message for first motor test.

        Returns:
            str: Safety warning message

        """
        return _(
            "IMPORTANT SAFETY WARNING:\n\n"
            "• Propellers MUST be removed\n"
            "• Vehicle MUST be secured\n"
            "• Stay clear of rotating parts\n"
            "• Emergency stop available at all times\n\n"
            "Do you want to proceed with motor testing?"
        )

    def get_battery_safety_message(self, reason: str) -> str:
        """
        Get battery-specific safety message.

        Args:
            reason: Safety check failure reason

        Returns:
            str: Battery safety message

        """
        return _(
            "Battery voltage is outside the safe range for motor testing.\n\n"
            "Please:\n"
            "• Connect a properly charged battery\n"
            "• Ensure battery voltage is within the safe operating range\n"
            "• Check BATT_ARM_VOLT and MOT_BAT_VOLT_MAX parameters\n\n"
            "Reason: %(reason)s"
        ) % {"reason": reason}

    def is_battery_related_safety_issue(self, reason: str) -> bool:
        """
        Check if safety issue is battery/voltage related.

        Args:
            reason: Safety check failure reason

        Returns:
            bool: True if battery/voltage related

        """
        return "voltage" in reason.lower() or "battery" in reason.lower()

    def get_current_frame_selection_text(self) -> str:
        """
        Get current frame configuration as selection text.

        Returns:
            str: Frame selection text in format "Type Name" (only type, since class is fixed)

        """
        current_types = self.get_current_frame_class_types()

        # Find type name for current frame type
        return current_types.get(self._frame_type, f"Type {self._frame_type}")

    def get_frame_type_pairs(self) -> list[tuple[str, str]]:
        """
        Get frame type options as (code, display_text) tuples for PairTupleCombobox.

        Returns:
            list[tuple[str, str]]: List of (type_code, "type_code: type_name") tuples

        """
        current_types = self.get_current_frame_class_types()

        # Convert to list of tuples with format: (code, "code: name")
        pairs = []
        for type_code, type_name in current_types.items():
            code_str = str(type_code)
            display_text = f"{type_code}: {type_name}"
            pairs.append((code_str, display_text))

        return pairs

    def get_current_frame_selection_key(self) -> str:
        """
        Get current frame type code as string key for PairTupleCombobox selection.

        Returns:
            str: Current frame type code as string

        """
        return str(self._frame_type)
