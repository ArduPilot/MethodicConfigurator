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
from os import path as os_path
from typing import Any, Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_json_with_schema import FilesystemJSONWithSchema
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController

# pylint: disable=too-many-lines


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

        # Initialize motor data loader for motor directions and test order
        self._motor_data_loader = FilesystemJSONWithSchema(
            json_filename="AP_Motors_test.json", schema_filename="AP_Motors_test_schema.json"
        )
        self._motor_data: dict = {}

        # Initialize frame configuration with defaults
        self._frame_class: int = 0  # Default to invalid
        self._frame_type: int = 0  # Default to invalid
        self._motor_count: int = 0  # Default to invalid
        self._frame_layout: dict[str, Any] = {}  # default to empty
        self._got_battery_status = False

        # Load motor configuration data
        self._load_motor_data()

        # Motor testing requires a connected flight controller for safety
        # We must fail early if the connection is not available
        self._update_frame_configuration()

    def _update_frame_configuration(self) -> None:
        """Update frame configuration from flight controller."""
        if self.flight_controller.master is None or not self.flight_controller.fc_parameters:
            msg = _("Flight controller connection required for motor testing")
            logging_error(msg)
            raise RuntimeError(msg)

        try:
            # Get from flight controller
            frame_class, frame_type = self.flight_controller.get_frame_info()
            if self._frame_class == frame_class and self._frame_type == frame_type:
                return
            self._frame_class = frame_class
            self._frame_type = frame_type
            self._motor_count = 0
            if self._motor_data_loader.data and "layouts" in self._motor_data_loader.data:
                # find a layout that matches the current frame class and type
                for layout in self._motor_data_loader.data["layouts"]:
                    if layout["Class"] == self._frame_class and layout["Type"] == self._frame_type and "motors" in layout:
                        self._frame_layout = layout
                        self._motor_count = len(layout["motors"])
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
        except Exception as e:
            logging_error(_("Failed to update frame configuration: %(error)s"), {"error": str(e)})
            raise

    def _load_motor_data(self) -> None:
        """Load motor configuration data from AP_Motors_test.json file."""
        try:
            # Get the directory where this module is located (contains the JSON files)
            current_dir = os_path.dirname(__file__)
            self._motor_data = self._motor_data_loader.load_json_data(current_dir)

            if not self._motor_data:
                logging_warning(_("Failed to load motor test data from AP_Motors_test.json"))
            else:
                logging_debug(
                    _("Successfully loaded motor test data with %(layouts)d layouts"),
                    {"layouts": len(self._motor_data.get("layouts", []))},
                )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Error loading motor test data: %(error)s"), {"error": str(e)})
            self._motor_data = {}

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
        Get motor numbers in test order (1, 4, 3, 2, etc.).

        Returns:
            list[int]: List of motor numbers (1-based) in their test order

        """
        motor_numbers: list[int] = [0] * self._motor_count
        if self._frame_layout:
            for motor in self._frame_layout.get("motors", []):
                test_order = motor.get("TestOrder")
                if test_order and 1 <= test_order <= self._motor_count:
                    motor_numbers[test_order - 1] = motor.get("Number")
            return motor_numbers
        err_msg = _("No Frame layout found, not possible to generate motor test order")
        raise ValueError(err_msg)

    def get_motor_directions(self) -> list[str]:
        """
        Get expected motor rotation directions based on frame configuration.

        Returns:
            list[str]: List of motor directions ("CW" or "CCW")

        """
        motor_directions: list[str] = [""] * self._motor_count
        if self._frame_layout:
            for motor in self._frame_layout.get("motors", []):
                test_order = motor.get("TestOrder")
                if test_order and 1 <= test_order <= self._motor_count:
                    motor_directions[test_order - 1] = motor.get("Rotation")
            return motor_directions
        err_msg = _("No Frame layout found, not possible to generate motor test rotation order")
        raise ValueError(err_msg)

    def is_battery_monitoring_enabled(self) -> bool:
        """
        Check if battery monitoring is enabled in the flight controller parameters.

        Returns:
            bool: True if battery monitoring is enabled, False otherwise.

        """
        if self.flight_controller.master is None:
            logging_warning(_("Flight controller not connected, cannot check battery monitoring status."))
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
            logging_warning(_("Flight controller not connected, cannot get battery status."))
            return None

        if not self.is_battery_monitoring_enabled():
            logging_warning(_("Battery monitoring disabled, cannot get battery status."))
            return None

        if not self._got_battery_status:
            self.flight_controller.request_periodic_battery_status(500000)

        battery_status, message = self.flight_controller.get_battery_status()
        if message:
            logging_debug(message)
        else:
            self._got_battery_status = True

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
        if not 1 <= throttle_percent <= 100:
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
        return self.flight_controller.test_motors_in_sequence(self.get_motor_count(), throttle_percent, timeout_seconds)

    def stop_all_motors(self) -> tuple[bool, str]:
        """
        Emergency stop for all motors.

        Returns:
            tuple[bool, str]: (success, error_message) - True on success with empty message,
                             False with error description on failure

        """
        return self.flight_controller.stop_all_motors()

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

    def get_test_duration(self) -> float:
        """
        Get the current motor test duration setting.

        Returns:
            float: Test duration in seconds

        """
        try:
            duration = ProgramSettings.get_setting("motor_test/duration")
            if duration is None:
                raise ReferenceError(_("Motor test duration setting not found"))
            duration = float(duration)
            if duration < 0.1:
                raise ValueError(_("Motor test duration must be at least 0.1 seconds"))
            if duration > 10.0:
                raise ValueError(_("Motor test duration must not exceed 10 seconds"))
            return duration
        except (ReferenceError, ValueError) as exc:
            logging_error(_("Invalid motor test duration setting: %(error)s"), {"error": str(exc)})
            raise exc

    def set_test_duration(self, duration: float) -> bool:
        """
        Set the motor test duration setting.

        Args:
            duration: Test duration in seconds

        Returns:
            bool: True if setting was saved successfully

        """
        try:
            if duration < 0.1:
                raise ValueError(_("Motor test duration must be at least 0.1 seconds"))
            if duration > 10.0:
                raise ValueError(_("Motor test duration must not exceed 10 seconds"))
            ProgramSettings.set_setting("motor_test/duration", duration)
            return True
        except ValueError as exc:
            logging_error(_("Invalid motor test duration setting: %(error)s"), {"error": str(exc)})
            return False
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to save duration setting: %(error)s"), {"error": str(exc)})
            return False

    def get_test_throttle_pct(self) -> int:
        """
        Get the current motor test throttle percentage setting.

        Returns:
            int: Throttle percentage (1-100)

        """
        try:
            throttle_pct = ProgramSettings.get_setting("motor_test/throttle_pct")
            if throttle_pct is None:
                raise ReferenceError(_("Motor test throttle percentage setting not found"))
            throttle_pct = int(throttle_pct)
            if throttle_pct < 1:
                raise ValueError(_("Motor test throttle percentage must be at least 1"))
            if throttle_pct > 100:
                raise ValueError(_("Motor test throttle percentage must not exceed 100"))
            return throttle_pct
        except (ReferenceError, ValueError) as exc:
            logging_error(_("Invalid motor test throttle percentage setting: %(error)s"), {"error": str(exc)})
            raise exc

    def set_test_throttle_pct(self, throttle_pct: int) -> bool:
        """
        Set the motor test throttle percentage setting.

        Args:
            throttle_pct: Throttle percentage (1-100)

        Returns:
            bool: True if setting was saved successfully

        """
        try:
            if throttle_pct < 1:
                raise ValueError(_("Motor test throttle percentage must be at least 1"))
            if throttle_pct > 100:
                raise ValueError(_("Motor test throttle percentage must not exceed 100"))
            ProgramSettings.set_setting("motor_test/throttle_pct", throttle_pct)
            return True
        except ValueError as exc:
            logging_error(_("Invalid motor test throttle percentage setting: %(error)s"), {"error": str(exc)})
            return False
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logging_error(_("Failed to save throttle percentage setting: %(error)s"), {"error": str(exc)})
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

            return True, ""

        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = _("Failed to update frame configuration: %(error)s") % {"error": str(e)}
            logging_error(error_msg)
            return False, error_msg

    def get_frame_options(self) -> dict[str, dict[int, str]]:  # pylint: disable=too-many-branches
        """
        Get all available frame configuration options.

        Uses motor data loader as the primary source, falling back to doc_dict if necessary.

        Returns:
            dict[str, dict[int, str]]: A dictionary of frame options grouped by class name.

        """
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

    def parse_frame_type_selection(self, selected_text: str) -> tuple[bool, int, int, str]:
        """
        Parse frame type selection text and return frame codes.

        Args:
            selected_text: Selected text in format "Frame Class: Frame Type"

        Returns:
            tuple[bool, int, int, str]: (success, frame_class_code, frame_type_code, error_message)

        """
        if ":" not in selected_text:
            return False, 0, 0, _("Invalid frame type format: %(text)s") % {"text": selected_text}

        try:
            frame_class_name, frame_type_name = selected_text.split(":", 1)
            frame_class_name = frame_class_name.strip()
            frame_type_name = frame_type_name.strip()

            # Get frame options to find the numeric codes
            frame_options = self.get_frame_options()

            # Find frame class code
            frame_class_code = None
            frame_type_code = None
            for class_name, types in frame_options.items():
                if class_name.upper() == frame_class_name.upper():
                    # Find frame type code within this class
                    for type_code, type_name in types.items():
                        if type_name.upper() == frame_type_name.upper():
                            frame_class_code = list(frame_options.keys()).index(class_name) + 1
                            frame_type_code = type_code
                            break
                    break

            if frame_class_code is None or frame_type_code is None:
                return False, 0, 0, _("Could not find frame configuration for: %(text)s") % {"text": selected_text}

            return True, frame_class_code, frame_type_code, ""

        except Exception as e:  # pylint: disable=broad-exception-caught
            return False, 0, 0, _("Error parsing frame type: %(error)s") % {"error": str(e)}

    def update_frame_type_from_selection(self, selected_text: str) -> tuple[bool, str]:
        """
        Update frame configuration based on user selection.

        Args:
            selected_text: Selected text in format "Frame Class: Frame Type"

        Returns:
            tuple[bool, str]: (success, error_message)

        """
        success, frame_class_code, frame_type_code, error_msg = self.parse_frame_type_selection(selected_text)
        if not success:
            return False, error_msg

        # Immediately upload parameters to flight controller
        success_class, msg_class = self.set_parameter("FRAME_CLASS", frame_class_code)
        success_type, msg_type = self.set_parameter("FRAME_TYPE", frame_type_code)

        if not success_class or not success_type:
            error_msg = _("Failed to update frame parameters:\n%(msg1)s\n%(msg2)s") % {
                "msg1": msg_class,
                "msg2": msg_type,
            }
            return False, error_msg

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
                if layout.get("Class") == frame_class_code and layout.get("Type") == frame_type_code and "motors" in layout:
                    self._frame_layout = layout
                    self._motor_count = len(layout["motors"])
                    break

        return True, ""

    def get_svg_scaling_info(
        self, canvas_width: int, canvas_height: int, svg_width: int, svg_height: int
    ) -> tuple[float, int]:
        """
        Calculate SVG scaling information for diagram display.

        Args:
            canvas_width: Canvas width in pixels
            canvas_height: Canvas height in pixels
            svg_width: SVG width in pixels
            svg_height: SVG height in pixels

        Returns:
            tuple[float, int]: (scale_factor, scaled_height)

        """
        if svg_width > 0 and svg_height > 0:
            scale_x = canvas_width / svg_width
            scale_y = canvas_height / svg_height
            scale = min(scale_x, scale_y) * 0.9  # Leave some margin
            scaled_height = int(svg_height * scale)
            return scale, scaled_height
        return 1.0, svg_height

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

    def validate_motor_test_parameters(self, throttle_percent: int, timeout_seconds: int) -> tuple[bool, str]:
        """
        Validate motor test parameters before execution.

        Args:
            throttle_percent: Throttle percentage (0-100)
            timeout_seconds: Test duration in seconds

        Returns:
            tuple[bool, str]: (is_valid, error_message)

        """
        if not 0 <= throttle_percent <= 100:
            return False, _("Throttle percentage must be between 0 and 100")

        if not 0.1 <= timeout_seconds <= 60:
            return False, _("Test duration must be between 0.1 and 60 seconds")

        return True, ""

    def should_show_first_test_warning(self) -> bool:
        """
        Check if first-time safety warning should be shown.

        Returns:
            bool: True if warning should be shown

        """
        # Could be expanded to check user preferences/settings
        return True

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
            str: Frame selection text in format "Class: Type"

        """
        frame_options = self.get_frame_options()

        # Find class name
        class_names = list(frame_options.keys())
        if self._frame_class <= len(class_names):
            class_name = class_names[self._frame_class - 1]

            # Find type name
            types = frame_options.get(class_name, {})
            type_name = types.get(self._frame_type, f"Type {self._frame_type}")

            return f"{class_name}: {type_name}"

        return f"Class {self._frame_class}: Type {self._frame_type}"
