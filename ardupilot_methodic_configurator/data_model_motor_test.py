"""
Data model for motor test functionality.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import debug as logging_debug
from logging import error as logging_error
from logging import info as logging_info
from logging import warning as logging_warning
from math import nan
from typing import Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController


class MotorTestDataModel:  # pylint: disable=too-many-public-methods
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
        settings: ProgramSettings,
    ) -> None:
        """
        Initialize the motor test data model.

        Args:
            flight_controller: Backend flight controller interface
            filesystem: Backend filesystem interface
            settings: Backend program settings interface

        """
        self.flight_controller = flight_controller
        self.filesystem = filesystem
        self.settings = settings

        # Initialize frame configuration
        self._frame_class: int = 1  # Default to QUAD
        self._frame_type: int = 1  # Default to X
        self._motor_count: int = 0

        # Update frame configuration from flight controller or defaults
        self._update_frame_configuration()

    def _update_frame_configuration(self) -> None:
        """Update frame configuration from flight controller."""
        if self.flight_controller.master is None or not self.flight_controller.fc_parameters:
            msg = _("Flight controller connection required for motor testing")
            logging_error(msg)
            raise RuntimeError(msg)

        try:
            # Get from flight controller
            self._frame_class, self._frame_type = self.flight_controller.get_frame_info()
            self._motor_count = self.flight_controller.get_motor_count_from_frame()

            logging_debug(
                _("Frame configuration updated: Class=%(class)d, Type=%(type)d, Motors=%(motors)d"),
                {
                    "class": self._frame_class,
                    "type": self._frame_type,
                    "motors": self._motor_count,
                },
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to update frame configuration: %(error)s"), {"error": str(e)})
            raise

    @property
    def frame_class(self) -> int:
        """Get the current frame class."""
        return self._frame_class

    @property
    def frame_type(self) -> int:
        """Get the current frame type."""
        return self._frame_type

    def get_motor_count(self) -> int:
        """
        Get the number of motors for the current frame configuration.

        Returns:
            int: Number of motors

        """
        return self._motor_count

    def get_motor_labels(self) -> list[str]:
        """
        Generate motor labels (A, B, C, D, etc.) based on motor count.

        Returns:
            list[str]: List of motor labels

        """
        return [chr(ord("A") + i) for i in range(self._motor_count)]

    def get_motor_numbers(self) -> list[int]:
        """
        Generate motor numbers (1, 2, 3, 4, etc.) based on motor count.

        Returns:
            list[int]: List of motor numbers (1-based)

        """
        return list(range(1, self._motor_count + 1))

    def is_battery_monitoring_enabled(self) -> bool:
        """
        Check if battery monitoring is enabled in the flight controller parameters.

        Returns:
            bool: True if battery monitoring is enabled, False otherwise.

        """
        if self.flight_controller.master is None:
            logging_warning("Flight controller not connected, cannot check battery monitoring status.")
            return False
        return self.flight_controller.is_battery_monitoring_enabled()

    def get_battery_status(self) -> Optional[tuple[float, float]]:
        """
        Get the current battery voltage and current.

        Returns:
            Optional[tuple[float, float]]: (voltage, current) in volts and amps,
                                         or None if not available

        """
        if self.flight_controller.master is None:
            logging_warning("Flight controller not connected, cannot get battery status.")
            return None

        if not self.is_battery_monitoring_enabled():
            return None

        battery_status, message = self.flight_controller.get_battery_status()
        if message:
            logging_debug(message)

        return battery_status

    def get_voltage_thresholds(self) -> tuple[float, float]:
        """
        Get battery voltage thresholds for motor testing safety.

        Returns:
            tuple[float, float]: (min_voltage, max_voltage) for safe motor testing

        """
        if self.flight_controller.master is None or not self.flight_controller.fc_parameters:
            logging_warning(_("Flight controller connection required for voltage threshold check"))
            return (nan, nan)

        return self.flight_controller.get_voltage_thresholds()

    def get_voltage_status(self) -> str:
        """
        Get the battery voltage status as a string.

        Returns:
            str: "safe", "unsafe", "disabled", or "unavailable"

        """
        if not self.is_battery_monitoring_enabled():
            return "disabled"

        battery_status = self.get_battery_status()
        if battery_status is None:
            return "unavailable"

        voltage, _current = battery_status
        min_voltage, max_voltage = self.get_voltage_thresholds()

        if min_voltage < voltage < max_voltage:
            return "safe"
        return "critical"

    def is_motor_test_safe(self) -> tuple[bool, str]:
        """
        Check if motor testing is currently safe.

        Returns:
            tuple[bool, str]: (is_safe, reason) - True if safe with empty reason,
                             False with explanation if unsafe

        """
        # Check if flight controller is connected
        if self.flight_controller.master is None:
            return False, _("Flight controller not connected.")

        # Check battery monitoring
        if not self.is_battery_monitoring_enabled():
            # If battery monitoring is disabled, assume it's safe but warn user
            return True, _("Battery monitoring disabled, cannot verify voltage.")

        # Check battery voltage if monitoring is enabled
        battery_status = self.get_battery_status()
        if battery_status is None:
            return False, _("Could not read battery status.")

        voltage, _current = battery_status
        min_voltage, max_voltage = self.get_voltage_thresholds()

        if not min_voltage < voltage < max_voltage:
            return False, _("Battery voltage %(voltage).1fV is outside safe range (%(min).1fV - %(max).1fV)") % {
                "voltage": voltage,
                "min": min_voltage,
                "max": max_voltage,
            }

        return True, ""

    def set_parameter(self, param_name: str, value: float) -> tuple[bool, str]:
        """
        Set a parameter value and upload to flight controller.

        Args:
            param_name: Parameter name (e.g., "MOT_SPIN_ARM")
            value: Parameter value

        Returns:
            tuple[bool, str]: (success, error_message) - True on success with empty message,
                             False with error description on failure

        """
        if self.flight_controller.master is None:
            error_msg = _("No flight controller connection available")
            return False, error_msg

        try:
            # Validate parameter bounds if possible
            if param_name in ["MOT_SPIN_ARM", "MOT_SPIN_MIN"] and not 0.0 <= value <= 1.0:
                error_msg = _("%(param)s value %(value).3f is outside valid range (0.0 - 1.0)") % {
                    "param": param_name,
                    "value": value,
                }
                return False, error_msg

            # Set parameter and verify it was set correctly
            self.flight_controller.set_param(param_name, value)
            # Read back the parameter to verify it was set correctly
            actual_value = self.get_parameter(param_name)
            if actual_value is not None and abs(actual_value - value) < 0.001:  # Allow small floating-point tolerance
                logging_info(_("Parameter %(param)s set to %(value).3f"), {"param": param_name, "value": value})
                return True, ""
            error_msg = _("Parameter %(param)s verification failed: expected %(expected).3f, got %(actual)s") % {
                "param": param_name,
                "expected": value,
                "actual": actual_value if actual_value is not None else "None",
            }
            return False, error_msg

        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = _("Error setting parameter %(param)s: %(error)s") % {
                "param": param_name,
                "error": str(e),
            }
            logging_error(error_msg)
            return False, error_msg

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

    def test_motor(self, motor_number: int, throttle_percent: int, timeout_seconds: int) -> tuple[bool, str]:
        """
        Test a specific motor.

        Args:
            motor_number: Motor number (1-based, as used by ArduPilot)
            throttle_percent: Throttle percentage (1-100)
            timeout_seconds: Test duration in seconds

        Returns:
            tuple[bool, str]: (success, error_message) - True on success with empty message,
                             False with error description on failure

        """
        # Safety check
        is_safe, safety_reason = self.is_motor_test_safe()
        if not is_safe:
            return False, safety_reason

        # Validate motor number
        if not 1 <= motor_number <= self._motor_count:
            error_msg = _("Invalid motor number %(number)d (valid range: 1-%(max)d)") % {
                "number": motor_number,
                "max": self._motor_count,
            }
            return False, error_msg

        # Validate throttle percentage
        if not 0 <= throttle_percent <= 100:
            error_msg = _("Invalid throttle percentage %(throttle)d (valid range: 1-100)") % {
                "throttle": throttle_percent,
            }
            return False, error_msg

        # Execute motor test
        return self.flight_controller.test_motor(motor_number, throttle_percent, timeout_seconds)

    def test_all_motors(self, throttle_percent: int, timeout_seconds: int) -> tuple[bool, str]:
        """
        Test all motors simultaneously.

        Args:
            throttle_percent: Throttle percentage (1-100)
            timeout_seconds: Test duration in seconds

        Returns:
            tuple[bool, str]: (success, error_message) - True on success with empty message,
                             False with error description on failure

        """
        # Safety check
        is_safe, safety_reason = self.is_motor_test_safe()
        if not is_safe:
            return False, safety_reason

        # Execute all motors test
        return self.flight_controller.test_all_motors(throttle_percent, timeout_seconds)

    def test_motors_in_sequence(self, throttle_percent: int, timeout_seconds: int) -> tuple[bool, str]:
        """
        Test motors in sequence (A, B, C, D, etc.).

        Args:
            throttle_percent: Throttle percentage (0-100)
            timeout_seconds: Test duration per motor in seconds

        Returns:
            tuple[bool, str]: (success, error_message) - True on success with empty message,
                             False with error description on failure

        """
        # Safety check
        is_safe, safety_reason = self.is_motor_test_safe()
        if not is_safe:
            return False, safety_reason

        # Execute sequential test
        return self.flight_controller.test_motors_in_sequence(throttle_percent, timeout_seconds)

    def stop_all_motors(self) -> tuple[bool, str]:
        """
        Emergency stop for all motors.

        Returns:
            tuple[bool, str]: (success, error_message) - True on success with empty message,
                             False with error description on failure

        """
        return self.flight_controller.stop_all_motors()

    def get_motor_diagram_path(self) -> str:
        """
        Get the filepath for the motor diagram SVG file for the current frame.

        Returns:
            str: Absolute path to the motor diagram SVG file, or empty string if not available

        """
        return ProgramSettings.motor_diagram_filepath(self._frame_class, self._frame_type)

    def motor_diagram_exists(self) -> bool:
        """
        Check if a motor diagram exists for the current frame configuration.

        Returns:
            bool: True if diagram exists, False otherwise

        """
        return ProgramSettings.motor_diagram_exists(self._frame_class, self._frame_type)

    def get_test_duration(self) -> float:
        """
        Get the current motor test duration setting.

        Returns:
            float: Test duration in seconds

        """
        return ProgramSettings.get_motor_test_duration()

    def set_test_duration(self, duration: float) -> bool:
        """
        Set the motor test duration setting.

        Args:
            duration: Test duration in seconds

        Returns:
            bool: True if setting was saved successfully

        """
        try:
            ProgramSettings.set_motor_test_duration(duration)
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to save test duration setting: %(error)s"), {"error": str(e)})
            return False

    def get_test_throttle_pct(self) -> int:
        """
        Get the current motor test throttle percentage setting.

        Returns:
            int: Throttle percentage (1-100)

        """
        return ProgramSettings.get_motor_test_throttle_pct()

    def set_test_throttle_pct(self, throttle: int) -> bool:
        """
        Set the motor test throttle percentage setting.

        Args:
            throttle: Throttle percentage (1-100)

        Returns:
            bool: True if setting was saved successfully

        """
        try:
            ProgramSettings.set_motor_test_throttle_pct(throttle)
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to save throttle percentage setting: %(error)s"), {"error": str(e)})
            return False

    def update_frame_configuration(self, frame_class: int, frame_type: int) -> tuple[bool, str]:
        """
        Update the frame configuration and upload to flight controller.

        Args:
            frame_class: New frame class
            frame_type: New frame type

        Returns:
            tuple[bool, str]: (success, error_message) - True on success with empty message,
                             False with error description on failure

        """
        if self.flight_controller.master is None or not self.flight_controller.fc_parameters:
            error_msg = _("Flight controller connection required for frame configuration update")
            return False, error_msg

        try:
            # Set FRAME_CLASS parameter
            class_success, class_error = self.set_parameter("FRAME_CLASS", float(frame_class))
            if not class_success:
                return False, class_error

            # Set FRAME_TYPE parameter
            type_success, type_error = self.set_parameter("FRAME_TYPE", float(frame_type))
            if not type_success:
                return False, type_error

            # Update internal state
            self._frame_class = frame_class
            self._frame_type = frame_type

            # Recalculate motor count
            self._motor_count = self.flight_controller.get_motor_count_from_frame()

            logging_info(
                _("Frame configuration updated: Class=%(class)d, Type=%(type)d, Motors=%(motors)d"),
                {
                    "class": self._frame_class,
                    "type": self._frame_type,
                    "motors": self._motor_count,
                },
            )

            return True, ""

        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = _("Failed to update frame configuration: %(error)s") % {"error": str(e)}
            logging_error(error_msg)
            return False, error_msg

    def get_frame_options(self) -> dict[str, dict[int, str]]:
        """
        Get available frame class and type options.

        Returns:
            dict[str, dict[int, str]]: Dictionary with 'classes' and 'types' keys,
                                      each containing id->name mappings

        """
        frame_classes = {
            1: _("Quad"),
            2: _("Hexa"),
            3: _("Octo"),
            4: _("Octo Quad"),
            5: _("Y6"),
            7: _("Tri"),
            10: _("Bicopter"),
            12: _("Dodeca Hexa"),
            14: _("Deca"),
        }

        frame_types = {
            0: _("Plus"),
            1: _("X"),
            2: _("V"),
            3: _("H"),
            4: _("V-tail"),
            5: _("A-tail"),
        }

        return {
            "classes": frame_classes,
            "types": frame_types,
        }

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
