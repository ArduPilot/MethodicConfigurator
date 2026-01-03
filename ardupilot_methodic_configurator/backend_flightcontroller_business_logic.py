"""
Pure business logic functions for flight controller operations.

This module contains stateless, side-effect-free functions that implement business rules
and calculations. These functions are easily testable without needing hardware or mocks.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Optional


def calculate_voltage_thresholds(fc_parameters: dict[str, float]) -> tuple[float, float]:
    """
    Calculate battery voltage thresholds for motor testing safety.

    This is a pure function that extracts the minimum and maximum voltage thresholds
    from flight controller parameters.

    Args:
        fc_parameters: Dictionary of flight controller parameters

    Returns:
        tuple[float, float]: (min_voltage, max_voltage) for safe motor testing

    Examples:
        >>> params = {"BATT_ARM_VOLT": 10.5, "MOT_BAT_VOLT_MAX": 25.2}
        >>> calculate_voltage_thresholds(params)
        (10.5, 25.2)

        >>> calculate_voltage_thresholds({})
        (0.0, 0.0)

    """
    min_voltage = fc_parameters.get("BATT_ARM_VOLT", 0.0)
    max_voltage = fc_parameters.get("MOT_BAT_VOLT_MAX", 0.0)
    return (min_voltage, max_voltage)


def is_battery_monitoring_enabled(fc_parameters: dict[str, float]) -> bool:
    """
    Check if battery monitoring is enabled in flight controller parameters.

    Args:
        fc_parameters: Dictionary of flight controller parameters

    Returns:
        bool: True if BATT_MONITOR != 0, False otherwise

    Examples:
        >>> is_battery_monitoring_enabled({"BATT_MONITOR": 4.0})
        True

        >>> is_battery_monitoring_enabled({"BATT_MONITOR": 0.0})
        False

        >>> is_battery_monitoring_enabled({})
        False

    """
    return fc_parameters.get("BATT_MONITOR", 0) != 0


def get_frame_info(fc_parameters: dict[str, float]) -> tuple[int, int]:
    """
    Extract frame class and frame type from flight controller parameters.

    Args:
        fc_parameters: Dictionary of flight controller parameters

    Returns:
        tuple[int, int]: (frame_class, frame_type)
            frame_class: Frame class (default: 1 = QUAD)
            frame_type: Frame type (default: 1 = X)

    Examples:
        >>> get_frame_info({"FRAME_CLASS": 1.0, "FRAME_TYPE": 3.0})
        (1, 3)

        >>> get_frame_info({})
        (1, 1)

    """
    frame_class = int(fc_parameters.get("FRAME_CLASS", 1))  # Default to QUAD
    frame_type = int(fc_parameters.get("FRAME_TYPE", 1))  # Default to X
    return (frame_class, frame_type)


def validate_battery_voltage(
    voltage: float,
    min_voltage: float,
    max_voltage: float,
) -> tuple[bool, Optional[str]]:
    """
    Validate if battery voltage is within safe operating range for motor testing.

    Args:
        voltage: Current battery voltage in volts
        min_voltage: Minimum safe voltage (BATT_ARM_VOLT)
        max_voltage: Maximum safe voltage (MOT_BAT_VOLT_MAX)

    Returns:
        tuple[bool, Optional[str]]: (is_valid, error_message)
            is_valid: True if voltage is within safe range
            error_message: None if valid, descriptive error message if invalid

    Examples:
        >>> validate_battery_voltage(12.6, 10.5, 25.2)
        (True, None)

        >>> validate_battery_voltage(9.0, 10.5, 25.2)
        (False, 'Battery voltage 9.00V is below minimum safe voltage 10.50V')

        >>> validate_battery_voltage(26.0, 10.5, 25.2)
        (False, 'Battery voltage 26.00V is above maximum safe voltage 25.20V')

    """
    if voltage < min_voltage:
        return False, f"Battery voltage {voltage:.2f}V is below minimum safe voltage {min_voltage:.2f}V"
    if voltage > max_voltage:
        return False, f"Battery voltage {voltage:.2f}V is above maximum safe voltage {max_voltage:.2f}V"
    return True, None


def convert_battery_telemetry_units(
    voltage_millivolts: int,
    current_centiamps: int,
) -> tuple[float, float]:
    """
    Convert battery telemetry from MAVLink units to standard units.

    Args:
        voltage_millivolts: Battery voltage in millivolts (MAVLink BATTERY_STATUS.voltages)
        current_centiamps: Battery current in centiamps (MAVLink BATTERY_STATUS.current_battery)

    Returns:
        tuple[float, float]: (voltage_volts, current_amps)
            voltage_volts: Voltage in volts
            current_amps: Current in amperes

    Examples:
        >>> convert_battery_telemetry_units(12600, 1050)
        (12.6, 10.5)

        >>> convert_battery_telemetry_units(-1, -1)  # Invalid/unavailable readings
        (0.0, 0.0)

    """
    voltage = voltage_millivolts / 1000.0 if voltage_millivolts != -1 else 0.0
    current = current_centiamps / 100.0 if current_centiamps != -1 else 0.0
    return (voltage, current)


def validate_throttle_percentage(throttle_percent: int) -> tuple[bool, Optional[str]]:
    """
    Validate throttle percentage is within safe range for motor testing.

    Args:
        throttle_percent: Throttle percentage (0-100)

    Returns:
        tuple[bool, Optional[str]]: (is_valid, error_message)
            is_valid: True if throttle is valid
            error_message: None if valid, descriptive error message if invalid

    Examples:
        >>> validate_throttle_percentage(50)
        (True, None)

        >>> validate_throttle_percentage(0)
        (True, None)

        >>> validate_throttle_percentage(-10)
        (False, 'Throttle percentage -10 is below minimum (0)')

        >>> validate_throttle_percentage(150)
        (False, 'Throttle percentage 150 is above maximum (100)')

    """
    if throttle_percent < 0:
        return False, f"Throttle percentage {throttle_percent} is below minimum (0)"
    if throttle_percent > 100:
        return False, f"Throttle percentage {throttle_percent} is above maximum (100)"
    return True, None


def validate_motor_test_duration(timeout_seconds: int) -> tuple[bool, Optional[str]]:
    """
    Validate motor test duration is within safe limits.

    Args:
        timeout_seconds: Test duration in seconds

    Returns:
        tuple[bool, Optional[str]]: (is_valid, error_message)
            is_valid: True if duration is valid
            error_message: None if valid, descriptive error message if invalid

    Examples:
        >>> validate_motor_test_duration(5)
        (True, None)

        >>> validate_motor_test_duration(0)
        (False, 'Motor test duration 0 seconds is too short (minimum: 1 second)')

        >>> validate_motor_test_duration(35)
        (False, 'Motor test duration 35 seconds is too long (maximum: 30 seconds)')

    """
    min_duration = 1
    max_duration = 30

    if timeout_seconds < min_duration:
        return False, f"Motor test duration {timeout_seconds} seconds is too short (minimum: {min_duration} second)"
    if timeout_seconds > max_duration:
        return False, f"Motor test duration {timeout_seconds} seconds is too long (maximum: {max_duration} seconds)"
    return True, None


def calculate_motor_sequence_number(motor_index: int, zero_based: bool = True) -> int:
    """
    Calculate MAVLink motor sequence number from motor index.

    ArduPilot motor test command uses 1-based sequence numbers,
    but motor indices are often 0-based in user interfaces.

    Args:
        motor_index: Motor index (0-based or 1-based depending on zero_based parameter)
        zero_based: If True, motor_index is 0-based; if False, motor_index is already 1-based

    Returns:
        int: MAVLink motor sequence number (1-based)

    Examples:
        >>> calculate_motor_sequence_number(0, zero_based=True)
        1

        >>> calculate_motor_sequence_number(3, zero_based=True)
        4

        >>> calculate_motor_sequence_number(1, zero_based=False)
        1

    """
    return motor_index + 1 if zero_based else motor_index
