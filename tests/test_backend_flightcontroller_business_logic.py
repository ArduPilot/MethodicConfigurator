#!/usr/bin/env python3

"""
Unit tests for pure business logic functions.

These tests verify the business logic without needing hardware or SITL.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller_business_logic import (
    calculate_motor_sequence_number,
    calculate_voltage_thresholds,
    convert_battery_telemetry_units,
    get_frame_info,
    is_battery_monitoring_enabled,
    validate_battery_voltage,
    validate_motor_test_duration,
    validate_throttle_percentage,
)


class TestVoltageThresholds:
    """Test battery voltage threshold calculations."""

    def test_with_valid_parameters(self) -> None:
        """
        Test voltage threshold extraction with valid parameters.

        Given a parameter dict with voltage thresholds
        When calculating thresholds
        Then correct min and max voltages are returned.
        """
        params = {"BATT_ARM_VOLT": 10.5, "MOT_BAT_VOLT_MAX": 25.2}
        min_v, max_v = calculate_voltage_thresholds(params)
        assert min_v == 10.5
        assert max_v == 25.2

    def test_with_missing_parameters(self) -> None:
        """
        Test voltage threshold extraction with missing parameters.

        Given an empty parameter dict
        When calculating thresholds
        Then default values (0.0) are returned.
        """
        min_v, max_v = calculate_voltage_thresholds({})
        assert min_v == 0.0
        assert max_v == 0.0

    def test_with_partial_parameters(self) -> None:
        """
        Test voltage threshold extraction with only one parameter.

        Given a parameter dict with only min voltage
        When calculating thresholds
        Then min voltage is returned and max is default.
        """
        params = {"BATT_ARM_VOLT": 11.1}
        min_v, max_v = calculate_voltage_thresholds(params)
        assert min_v == 11.1
        assert max_v == 0.0


class TestBatteryMonitoring:
    """Test battery monitoring enabled check."""

    def test_monitoring_enabled(self) -> None:
        """
        Test battery monitoring detection when enabled.

        Given BATT_MONITOR is non-zero
        When checking if monitoring is enabled
        Then True is returned.
        """
        assert is_battery_monitoring_enabled({"BATT_MONITOR": 4.0}) is True
        assert is_battery_monitoring_enabled({"BATT_MONITOR": 1.0}) is True

    def test_monitoring_disabled(self) -> None:
        """
        Test battery monitoring detection when disabled.

        Given BATT_MONITOR is zero
        When checking if monitoring is enabled
        Then False is returned.
        """
        assert is_battery_monitoring_enabled({"BATT_MONITOR": 0.0}) is False

    def test_monitoring_missing_parameter(self) -> None:
        """
        Test battery monitoring with missing parameter.

        Given BATT_MONITOR is not in parameters
        When checking if monitoring is enabled
        Then False is returned (default).
        """
        assert is_battery_monitoring_enabled({}) is False


class TestFrameInfo:
    """Test frame information extraction."""

    def test_with_valid_parameters(self) -> None:
        """
        Test frame info extraction with valid parameters.

        Given parameters with frame class and type
        When extracting frame info
        Then correct class and type are returned as integers.
        """
        params = {"FRAME_CLASS": 1.0, "FRAME_TYPE": 3.0}
        frame_class, frame_type = get_frame_info(params)
        assert frame_class == 1
        assert frame_type == 3

    def test_with_default_values(self) -> None:
        """
        Test frame info extraction with missing parameters.

        Given empty parameter dict
        When extracting frame info
        Then default values (1, 1) are returned.
        """
        frame_class, frame_type = get_frame_info({})
        assert frame_class == 1  # Default QUAD
        assert frame_type == 1  # Default X


class TestBatteryVoltageValidation:
    """Test battery voltage validation logic."""

    def test_voltage_in_range(self) -> None:
        """
        Test voltage validation when within range.

        Given voltage between min and max
        When validating
        Then validation passes with no error.
        """
        is_valid, error = validate_battery_voltage(12.6, 10.5, 25.2)
        assert is_valid is True
        assert error is None

    def test_voltage_below_minimum(self) -> None:
        """
        Test voltage validation when below minimum.

        Given voltage below min threshold
        When validating
        Then validation fails with descriptive error.
        """
        is_valid, error = validate_battery_voltage(9.0, 10.5, 25.2)
        assert is_valid is False
        assert error is not None
        assert "below minimum" in error
        assert "9.00" in error
        assert "10.50" in error

    def test_voltage_above_maximum(self) -> None:
        """
        Test voltage validation when above maximum.

        Given voltage above max threshold
        When validating
        Then validation fails with descriptive error.
        """
        is_valid, error = validate_battery_voltage(26.0, 10.5, 25.2)
        assert is_valid is False
        assert error is not None
        assert "above maximum" in error
        assert "26.00" in error
        assert "25.20" in error

    def test_voltage_at_boundaries(self) -> None:
        """
        Test voltage validation at exact boundaries.

        Given voltage exactly at min or max
        When validating
        Then validation passes (boundaries are inclusive).
        """
        assert validate_battery_voltage(10.5, 10.5, 25.2)[0] is True
        assert validate_battery_voltage(25.2, 10.5, 25.2)[0] is True


class TestBatteryTelemetryConversion:
    """Test battery telemetry unit conversions."""

    def test_valid_telemetry(self) -> None:
        """
        Test conversion of valid telemetry values.

        Given millivolts and centiamps
        When converting to standard units
        Then volts and amps are returned.
        """
        voltage, current = convert_battery_telemetry_units(12600, 1050)
        assert voltage == pytest.approx(12.6)
        assert current == pytest.approx(10.5)

    def test_invalid_telemetry(self) -> None:
        """
        Test conversion of invalid telemetry markers (-1).

        Given -1 values (MAVLink "not available" marker)
        When converting
        Then 0.0 is returned for both.
        """
        voltage, current = convert_battery_telemetry_units(-1, -1)
        assert voltage == 0.0
        assert current == 0.0

    def test_mixed_validity(self) -> None:
        """
        Test conversion with one valid and one invalid value.

        Given valid voltage but invalid current
        When converting
        Then voltage is converted, current is 0.
        """
        voltage, current = convert_battery_telemetry_units(11100, -1)
        assert voltage == pytest.approx(11.1)
        assert current == 0.0


class TestThrottleValidation:
    """Test throttle percentage validation."""

    def test_valid_throttle(self) -> None:
        """
        Test validation of valid throttle percentages.

        Given throttle in range 0-100
        When validating
        Then validation passes.
        """
        assert validate_throttle_percentage(0)[0] is True
        assert validate_throttle_percentage(50)[0] is True
        assert validate_throttle_percentage(100)[0] is True

    def test_throttle_below_minimum(self) -> None:
        """
        Test validation of negative throttle.

        Given negative throttle value
        When validating
        Then validation fails with error message.
        """
        is_valid, error = validate_throttle_percentage(-10)
        assert is_valid is False
        assert error is not None
        assert "below minimum" in error

    def test_throttle_above_maximum(self) -> None:
        """
        Test validation of excessive throttle.

        Given throttle above 100
        When validating
        Then validation fails with error message.
        """
        is_valid, error = validate_throttle_percentage(150)
        assert is_valid is False
        assert error is not None
        assert "above maximum" in error


class TestMotorTestDurationValidation:
    """Test motor test duration validation."""

    def test_valid_duration(self) -> None:
        """
        Test validation of valid test durations.

        Given duration in safe range (1-30 seconds)
        When validating
        Then validation passes.
        """
        assert validate_motor_test_duration(1)[0] is True
        assert validate_motor_test_duration(5)[0] is True
        assert validate_motor_test_duration(30)[0] is True

    def test_duration_too_short(self) -> None:
        """
        Test validation of too-short duration.

        Given duration of 0 seconds
        When validating
        Then validation fails.
        """
        is_valid, error = validate_motor_test_duration(0)
        assert is_valid is False
        assert error is not None
        assert "too short" in error

    def test_duration_too_long(self) -> None:
        """
        Test validation of excessive duration.

        Given duration above 30 seconds
        When validating
        Then validation fails.
        """
        is_valid, error = validate_motor_test_duration(35)
        assert is_valid is False
        assert error is not None
        assert "too long" in error


class TestMotorSequenceNumber:
    """Test motor sequence number calculation."""

    def test_zero_based_index(self) -> None:
        """
        Test conversion from 0-based index.

        Given 0-based motor index
        When calculating sequence number
        Then 1-based sequence is returned.
        """
        assert calculate_motor_sequence_number(0, zero_based=True) == 1
        assert calculate_motor_sequence_number(3, zero_based=True) == 4

    def test_one_based_index(self) -> None:
        """
        Test passthrough of 1-based index.

        Given already 1-based motor index
        When calculating sequence number
        Then same number is returned.
        """
        assert calculate_motor_sequence_number(1, zero_based=False) == 1
        assert calculate_motor_sequence_number(4, zero_based=False) == 4
