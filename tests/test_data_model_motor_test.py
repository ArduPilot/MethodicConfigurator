#!/usr/bin/env python3

"""
Tests for the data_model_motor_test.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.data_model_motor_test import MotorTestDataModel

# pylint: disable=too-many-lines,redefined-outer-name


# ==================== FIXTURES ====================


@pytest.fixture
def mock_flight_controller() -> MagicMock:
    """Fixture providing a mock flight controller with realistic test data."""
    fc = MagicMock(spec=FlightController)
    fc.master = MagicMock()  # Simulate connected state
    fc.fc_parameters = {
        "FRAME_CLASS": 1,
        "FRAME_TYPE": 1,
        "BATT_MONITOR": 4,
        "BATT_ARM_VOLT": 11.0,
        "MOT_BAT_VOLT_MAX": 16.8,
        "MOT_SPIN_ARM": 0.10,
        "MOT_SPIN_MIN": 0.15,
    }

    # Configure frame info and motor count
    fc.get_frame_info.return_value = (1, 1)  # Quad X
    fc.get_motor_count_from_frame.return_value = 4
    fc.is_battery_monitoring_enabled.return_value = True
    fc.get_battery_status.return_value = ((12.4, 2.1), "")
    fc.get_voltage_thresholds.return_value = (11.0, 16.8)

    # Configure motor test methods
    fc.test_motor.return_value = (True, "")
    fc.test_all_motors.return_value = (True, "")
    fc.test_motors_in_sequence.return_value = (True, "")
    fc.stop_all_motors.return_value = (True, "")
    fc.set_param.return_value = True

    return fc


@pytest.fixture
def mock_filesystem() -> MagicMock:
    """Fixture providing a mock filesystem with realistic test data."""
    return MagicMock(spec=LocalFilesystem)


@pytest.fixture
def mock_settings() -> MagicMock:
    """Fixture providing mock program settings."""
    return MagicMock(spec=ProgramSettings)


@pytest.fixture
def motor_test_model(mock_flight_controller, mock_filesystem, mock_settings) -> MotorTestDataModel:
    """Fixture providing a properly configured motor test data model for behavior testing."""
    return MotorTestDataModel(flight_controller=mock_flight_controller, filesystem=mock_filesystem, settings=mock_settings)


@pytest.fixture
def disconnected_flight_controller() -> MagicMock:
    """Fixture providing a disconnected flight controller for testing error scenarios."""
    fc = MagicMock(spec=FlightController)
    fc.master = None  # Simulate disconnected state
    fc.fc_parameters = None
    return fc


# ==================== INITIALIZATION TESTS ====================


class TestMotorTestDataModelInitialization:
    """Test motor test data model initialization and configuration."""

    def test_user_can_initialize_model_with_connected_flight_controller(
        self, mock_flight_controller, mock_filesystem, mock_settings
    ) -> None:
        """
        User can successfully initialize motor test model with connected flight controller.

        GIVEN: A connected flight controller with valid frame configuration
        WHEN: User initializes the motor test data model
        THEN: Model should be configured with correct frame settings
        """
        # Arrange: Flight controller already configured in fixture

        # Act: Initialize the model
        model = MotorTestDataModel(
            flight_controller=mock_flight_controller, filesystem=mock_filesystem, settings=mock_settings
        )

        # Assert: Frame configuration loaded correctly
        assert model.frame_class == 1
        assert model.frame_type == 1
        assert model.get_motor_count() == 4
        mock_flight_controller.get_frame_info.assert_called_once()
        mock_flight_controller.get_motor_count_from_frame.assert_called_once()

    def test_model_initialization_fails_with_disconnected_flight_controller(
        self, disconnected_flight_controller, mock_filesystem, mock_settings
    ) -> None:
        """
        Model initialization fails gracefully when flight controller is disconnected.

        GIVEN: A disconnected flight controller
        WHEN: User attempts to initialize the motor test data model
        THEN: Should raise RuntimeError with clear message
        """
        # Arrange: Disconnected flight controller configured in fixture

        # Act & Assert: Initialization should fail
        with pytest.raises(RuntimeError, match="Flight controller connection required for motor testing"):
            MotorTestDataModel(
                flight_controller=disconnected_flight_controller, filesystem=mock_filesystem, settings=mock_settings
            )

    def test_frame_configuration_update_failure_in_init(self) -> None:
        """
        Frame configuration update failure during initialization raises exception.

        GIVEN: A flight controller that throws an exception during frame info retrieval
        WHEN: Initializing the motor test model
        THEN: Should raise RuntimeError with proper logging
        """
        # Arrange: Mock flight controller with connection but failing frame info
        mock_fc = MagicMock(spec=FlightController)
        mock_fc.master = MagicMock()  # Connection exists
        mock_fc.fc_parameters = {"FRAME_CLASS": 1}  # Parameters exist
        mock_fc.get_frame_info.side_effect = Exception("Frame info error")

        mock_filesystem = MagicMock(spec=LocalFilesystem)
        mock_settings = MagicMock(spec=ProgramSettings)

        # Act & Assert: Exception should be raised
        with pytest.raises(Exception, match="Frame info error"):
            MotorTestDataModel(mock_fc, mock_filesystem, mock_settings)


class TestMotorTestDataModelFrameConfiguration:
    """Test frame configuration management and motor counting."""

    def test_user_can_get_motor_labels_for_current_frame(self, motor_test_model) -> None:
        """
        User can retrieve correct motor labels based on frame configuration.

        GIVEN: A motor test model with 4-motor frame configuration
        WHEN: User requests motor labels
        THEN: Should return labels A, B, C, D
        """
        # Arrange: Model configured with 4 motors in fixture

        # Act: Get motor labels
        labels = motor_test_model.get_motor_labels()

        # Assert: Correct labels returned
        assert labels == ["A", "B", "C", "D"]

    def test_user_can_get_motor_numbers_for_current_frame(self, motor_test_model) -> None:
        """
        User can retrieve correct motor numbers based on frame configuration.

        GIVEN: A motor test model with 4-motor frame configuration
        WHEN: User requests motor numbers
        THEN: Should return numbers 1, 2, 3, 4
        """
        # Arrange: Model configured with 4 motors in fixture

        # Act: Get motor numbers
        numbers = motor_test_model.get_motor_numbers()

        # Assert: Correct numbers returned
        assert numbers == [1, 2, 3, 4]

    def test_user_can_update_frame_configuration_successfully(self, motor_test_model) -> None:
        """
        User can successfully update frame configuration and motor count.

        GIVEN: A motor test model with current frame configuration
        WHEN: User updates frame class and type
        THEN: Frame should be updated and motor count recalculated
        """
        # Arrange: Configure updated motor count and parameter verification
        motor_test_model.flight_controller.get_motor_count_from_frame.return_value = 6

        # Mock parameter setting to update the fc_parameters dictionary
        def mock_set_param(param_name, value) -> bool:
            motor_test_model.flight_controller.fc_parameters[param_name] = value
            return True

        motor_test_model.flight_controller.set_param.side_effect = mock_set_param

        # Act: Update frame configuration
        success, error = motor_test_model.update_frame_configuration(frame_class=2, frame_type=1)

        # Assert: Configuration updated successfully
        assert success is True
        assert error == ""
        assert motor_test_model.frame_class == 2
        assert motor_test_model.frame_type == 1
        assert motor_test_model.get_motor_count() == 6

    def test_frame_configuration_update_fails_with_disconnected_controller(
        self, disconnected_flight_controller, mock_filesystem, mock_settings
    ) -> None:
        """
        Frame configuration update fails when flight controller is disconnected.

        GIVEN: A motor test model with disconnected flight controller
        WHEN: User attempts to update frame configuration
        THEN: Should return failure with clear error message
        """
        # Arrange: Create model with disconnected FC (will fail initialization)
        # We'll test this by mocking the model's flight controller directly
        with patch("ardupilot_methodic_configurator.data_model_motor_test.MotorTestDataModel._update_frame_configuration"):
            model = MotorTestDataModel(
                flight_controller=disconnected_flight_controller, filesystem=mock_filesystem, settings=mock_settings
            )
            model.flight_controller = disconnected_flight_controller

            # Act: Attempt frame configuration update
            success, error = model.update_frame_configuration(frame_class=2, frame_type=1)

            # Assert: Update failed with appropriate error
            assert success is False
            assert "Flight controller connection required" in error


class TestMotorTestDataModelBatteryMonitoring:
    """Test battery monitoring and safety validation."""

    def test_user_can_check_battery_monitoring_status_when_enabled(self, motor_test_model) -> None:
        """
        User can verify battery monitoring is enabled when BATT_MONITOR is configured.

        GIVEN: A flight controller with battery monitoring enabled
        WHEN: User checks battery monitoring status
        THEN: Should return True
        """
        # Arrange: Battery monitoring configured in fixture

        # Act: Check battery monitoring status
        is_enabled = motor_test_model.is_battery_monitoring_enabled()

        # Assert: Battery monitoring is enabled
        assert is_enabled is True
        motor_test_model.flight_controller.is_battery_monitoring_enabled.assert_called_once()

    def test_user_can_get_current_battery_status(self, motor_test_model) -> None:
        """
        User can retrieve current battery voltage and current readings.

        GIVEN: A flight controller with battery monitoring enabled
        WHEN: User requests battery status
        THEN: Should return voltage and current values
        """
        # Arrange: Battery status configured in fixture

        # Act: Get battery status
        status = motor_test_model.get_battery_status()

        # Assert: Battery status returned correctly
        assert status == (12.4, 2.1)
        motor_test_model.flight_controller.get_battery_status.assert_called_once()

    def test_user_gets_no_battery_status_when_monitoring_disabled(self, motor_test_model) -> None:
        """
        User gets no battery status when monitoring is disabled.

        GIVEN: A flight controller with battery monitoring disabled
        WHEN: User requests battery status
        THEN: Should return None
        """
        # Arrange: Disable battery monitoring
        motor_test_model.flight_controller.is_battery_monitoring_enabled.return_value = False

        # Act: Get battery status
        status = motor_test_model.get_battery_status()

        # Assert: No battery status available
        assert status is None

    def test_user_can_get_voltage_thresholds_for_safety(self, motor_test_model) -> None:
        """
        User can retrieve voltage thresholds for motor testing safety.

        GIVEN: A flight controller with configured voltage thresholds
        WHEN: User requests voltage thresholds
        THEN: Should return min and max voltage values
        """
        # Arrange: Voltage thresholds configured in fixture

        # Act: Get voltage thresholds
        min_voltage, max_voltage = motor_test_model.get_voltage_thresholds()

        # Assert: Correct thresholds returned
        assert min_voltage == 11.0
        assert max_voltage == 16.8
        motor_test_model.flight_controller.get_voltage_thresholds.assert_called_once()

    def test_user_gets_safe_voltage_status_within_thresholds(self, motor_test_model) -> None:
        """
        User gets safe voltage status when battery is within acceptable range.

        GIVEN: A battery voltage within safe operating range
        WHEN: User checks voltage status
        THEN: Should return "safe"
        """
        # Arrange: Battery voltage within safe range (fixture: 12.4V, range: 11.0-16.8V)

        # Act: Get voltage status
        status = motor_test_model.get_voltage_status()

        # Assert: Status is safe
        assert status == "safe"

    def test_user_gets_critical_voltage_status_outside_thresholds(self, motor_test_model) -> None:
        """
        User gets critical voltage status when battery voltage is outside safe range.

        GIVEN: A battery voltage outside safe operating range
        WHEN: User checks voltage status
        THEN: Should return "critical"
        """
        # Arrange: Set voltage outside safe range
        motor_test_model.flight_controller.get_battery_status.return_value = ((10.0, 2.1), "")

        # Act: Get voltage status
        status = motor_test_model.get_voltage_status()

        # Assert: Status is critical
        assert status == "critical"

    def test_user_gets_disabled_voltage_status_when_monitoring_disabled(self, motor_test_model) -> None:
        """
        User gets disabled voltage status when battery monitoring is off.

        GIVEN: A flight controller with battery monitoring disabled
        WHEN: User checks voltage status
        THEN: Should return "disabled"
        """
        # Arrange: Disable battery monitoring
        motor_test_model.flight_controller.is_battery_monitoring_enabled.return_value = False

        # Act: Get voltage status
        status = motor_test_model.get_voltage_status()

        # Assert: Status is disabled
        assert status == "disabled"


class TestMotorTestDataModelSafetyValidation:
    """Test motor testing safety validation logic."""

    def test_motor_testing_is_safe_with_good_conditions(self, motor_test_model) -> None:
        """
        Motor testing is considered safe under normal operating conditions.

        GIVEN: Connected flight controller with battery monitoring and safe voltage
        WHEN: User checks if motor testing is safe
        THEN: Should return True with empty reason
        """
        # Arrange: Good conditions configured in fixture

        # Act: Check motor test safety
        is_safe, reason = motor_test_model.is_motor_test_safe()

        # Assert: Motor testing is safe
        assert is_safe is True
        assert reason == ""

    def test_motor_testing_unsafe_with_disconnected_controller(self, motor_test_model) -> None:
        """
        Motor testing is unsafe when flight controller is disconnected.

        GIVEN: A disconnected flight controller
        WHEN: User checks if motor testing is safe
        THEN: Should return False with connection error message
        """
        # Arrange: Disconnect flight controller
        motor_test_model.flight_controller.master = None

        # Act: Check motor test safety
        is_safe, reason = motor_test_model.is_motor_test_safe()

        # Assert: Motor testing is unsafe
        assert is_safe is False
        assert "Flight controller not connected." in reason

    def test_motor_testing_safe_with_battery_monitoring_disabled(self, motor_test_model) -> None:
        """
        Motor testing is conditionally safe when battery monitoring is disabled.

        GIVEN: A connected flight controller with battery monitoring disabled
        WHEN: User checks if motor testing is safe
        THEN: Should return True with warning message
        """
        # Arrange: Disable battery monitoring
        motor_test_model.flight_controller.is_battery_monitoring_enabled.return_value = False

        # Act: Check motor test safety
        is_safe, reason = motor_test_model.is_motor_test_safe()

        # Assert: Motor testing is conditionally safe
        assert is_safe is True
        assert "Battery monitoring disabled" in reason

    def test_motor_testing_unsafe_with_low_voltage(self, motor_test_model) -> None:
        """
        Motor testing is unsafe when battery voltage is too low.

        GIVEN: A battery voltage below safe threshold
        WHEN: User checks if motor testing is safe
        THEN: Should return False with voltage warning
        """
        # Arrange: Set low battery voltage
        motor_test_model.flight_controller.get_battery_status.return_value = ((10.0, 2.1), "")

        # Act: Check motor test safety
        is_safe, reason = motor_test_model.is_motor_test_safe()

        # Assert: Motor testing is unsafe
        assert is_safe is False
        assert "Battery voltage 10.0V is outside safe range" in reason

    def test_motor_testing_unsafe_when_battery_status_unavailable(self, motor_test_model) -> None:
        """
        Motor testing is unsafe when battery status cannot be read.

        GIVEN: Battery monitoring enabled but status unavailable
        WHEN: User checks if motor testing is safe
        THEN: Should return False with status error
        """
        # Arrange: Make battery status unavailable
        motor_test_model.flight_controller.get_battery_status.return_value = (None, "Communication error")

        # Act: Check motor test safety
        is_safe, reason = motor_test_model.is_motor_test_safe()

        # Assert: Motor testing is unsafe
        assert is_safe is False
        assert "Could not read battery status" in reason


class TestMotorTestDataModelParameterManagement:
    """Test parameter setting and validation."""

    def test_user_can_set_motor_parameter_successfully(self, motor_test_model) -> None:
        """
        User can successfully set motor parameters with verification.

        GIVEN: A connected flight controller and valid parameter
        WHEN: User sets a motor parameter
        THEN: Parameter should be set and verified successfully
        """
        # Arrange: Configure parameter reading
        motor_test_model.flight_controller.fc_parameters["MOT_SPIN_ARM"] = 0.12

        # Act: Set parameter
        success, error = motor_test_model.set_parameter("MOT_SPIN_ARM", 0.12)

        # Assert: Parameter set successfully
        assert success is True
        assert error == ""
        motor_test_model.flight_controller.set_param.assert_called_once_with("MOT_SPIN_ARM", 0.12)

    def test_parameter_setting_fails_with_disconnected_controller(self, motor_test_model) -> None:
        """
        Parameter setting fails when flight controller is disconnected.

        GIVEN: A disconnected flight controller
        WHEN: User attempts to set a parameter
        THEN: Should return failure with connection error
        """
        # Arrange: Disconnect flight controller
        motor_test_model.flight_controller.master = None

        # Act: Attempt to set parameter
        success, error = motor_test_model.set_parameter("MOT_SPIN_ARM", 0.12)

        # Assert: Parameter setting failed
        assert success is False
        assert "No flight controller connection available" in error

    def test_parameter_validation_rejects_out_of_bounds_values(self, motor_test_model) -> None:
        """
        Parameter validation rejects values outside acceptable range.

        GIVEN: A motor parameter with defined bounds
        WHEN: User attempts to set value outside bounds
        THEN: Should return failure with validation error
        """
        # Arrange: Parameter bounds defined in code (0.0 - 1.0)

        # Act: Attempt to set out-of-bounds value
        success, error = motor_test_model.set_parameter("MOT_SPIN_ARM", 1.5)

        # Assert: Parameter validation failed
        assert success is False
        assert "outside valid range (0.0 - 1.0)" in error

    def test_parameter_verification_detects_setting_failure(self, motor_test_model) -> None:
        """
        Parameter verification detects when setting appears successful but value differs.

        GIVEN: A parameter that appears to set but reads back differently
        WHEN: User sets the parameter
        THEN: Should return failure with verification error
        """
        # Arrange: Simulate verification failure
        motor_test_model.flight_controller.fc_parameters["MOT_SPIN_ARM"] = 0.10  # Different from set value

        # Act: Set parameter with different result
        success, error = motor_test_model.set_parameter("MOT_SPIN_ARM", 0.12)

        # Assert: Verification failed
        assert success is False
        assert "verification failed" in error
        assert "expected 0.120, got 0.1" in error

    def test_user_can_get_parameter_value(self, motor_test_model) -> None:
        """
        User can retrieve current parameter values from flight controller.

        GIVEN: A flight controller with configured parameters
        WHEN: User requests a parameter value
        THEN: Should return the current value
        """
        # Arrange: Parameter configured in fixture

        # Act: Get parameter value
        value = motor_test_model.get_parameter("MOT_SPIN_ARM")

        # Assert: Correct value returned
        assert value == 0.10

    def test_parameter_retrieval_returns_none_for_disconnected_controller(self, motor_test_model) -> None:
        """
        Parameter retrieval returns None when flight controller is disconnected.

        GIVEN: A disconnected flight controller
        WHEN: User requests a parameter value
        THEN: Should return None
        """
        # Arrange: Disconnect flight controller
        motor_test_model.flight_controller.master = None
        motor_test_model.flight_controller.fc_parameters = None

        # Act: Get parameter value
        value = motor_test_model.get_parameter("MOT_SPIN_ARM")

        # Assert: No value available
        assert value is None


class TestMotorTestDataModelMotorTesting:
    """Test motor testing commands and validation."""

    def test_user_can_test_individual_motor_successfully(self, motor_test_model) -> None:
        """
        User can successfully test an individual motor with safety validation.

        GIVEN: Safe conditions for motor testing
        WHEN: User tests a specific motor
        THEN: Motor test should execute successfully
        """
        # Arrange: Safe conditions configured in fixture

        # Act: Test individual motor
        success, error = motor_test_model.test_motor(motor_number=1, throttle_percent=10, timeout_seconds=2)

        # Assert: Motor test successful
        assert success is True
        assert error == ""
        motor_test_model.flight_controller.test_motor.assert_called_once_with(1, 10, 2)

    def test_motor_test_fails_with_invalid_motor_number(self, motor_test_model) -> None:
        """
        Motor test fails when user specifies invalid motor number.

        GIVEN: A 4-motor vehicle configuration
        WHEN: User attempts to test motor number outside valid range
        THEN: Should return failure with validation error
        """
        # Arrange: 4-motor configuration in fixture

        # Act: Test invalid motor number
        success, error = motor_test_model.test_motor(motor_number=5, throttle_percent=10, timeout_seconds=2)

        # Assert: Motor test failed
        assert success is False
        assert "Invalid motor number 5 (valid range: 1-4)" in error

    def test_motor_test_fails_with_invalid_throttle_percentage(self, motor_test_model) -> None:
        """
        Motor test fails when user specifies invalid throttle percentage.

        GIVEN: Safe conditions for motor testing
        WHEN: User attempts test with throttle outside valid range
        THEN: Should return failure with validation error
        """
        # Arrange: Safe conditions configured in fixture

        # Act: Test with invalid throttle
        success, error = motor_test_model.test_motor(motor_number=1, throttle_percent=150, timeout_seconds=2)

        # Assert: Motor test failed
        assert success is False
        assert "Invalid throttle percentage 150 (valid range: 1-100)" in error

    def test_motor_test_fails_under_unsafe_conditions(self, motor_test_model) -> None:
        """
        Motor test fails when safety conditions are not met.

        GIVEN: Unsafe battery voltage conditions
        WHEN: User attempts motor test
        THEN: Should return failure with safety error
        """
        # Arrange: Set unsafe battery voltage
        motor_test_model.flight_controller.get_battery_status.return_value = ((10.0, 2.1), "")

        # Act: Attempt motor test
        success, error = motor_test_model.test_motor(motor_number=1, throttle_percent=10, timeout_seconds=2)

        # Assert: Motor test failed due to safety
        assert success is False
        assert "Battery voltage 10.0V is outside safe range" in error

    def test_user_can_test_all_motors_simultaneously(self, motor_test_model) -> None:
        """
        User can successfully test all motors simultaneously.

        GIVEN: Safe conditions for motor testing
        WHEN: User tests all motors
        THEN: All motors test should execute successfully
        """
        # Arrange: Safe conditions configured in fixture

        # Act: Test all motors
        success, error = motor_test_model.test_all_motors(throttle_percent=10, timeout_seconds=2)

        # Assert: All motors test successful
        assert success is True
        assert error == ""
        motor_test_model.flight_controller.test_all_motors.assert_called_once_with(10, 2)

    def test_user_can_test_motors_in_sequence(self, motor_test_model) -> None:
        """
        User can successfully test motors in sequence.

        GIVEN: Safe conditions for motor testing
        WHEN: User tests motors in sequence
        THEN: Sequential test should execute successfully
        """
        # Arrange: Safe conditions configured in fixture

        # Act: Test motors in sequence
        success, error = motor_test_model.test_motors_in_sequence(throttle_percent=10, timeout_seconds=2)

        # Assert: Sequential test successful
        assert success is True
        assert error == ""
        motor_test_model.flight_controller.test_motors_in_sequence.assert_called_once_with(10, 2)

    def test_user_can_stop_all_motors_emergency(self, motor_test_model) -> None:
        """
        User can emergency stop all motors at any time.

        GIVEN: Motors potentially running
        WHEN: User triggers emergency stop
        THEN: All motors should stop immediately
        """
        # Arrange: No special setup needed

        # Act: Emergency stop
        success, error = motor_test_model.stop_all_motors()

        # Assert: Emergency stop successful
        assert success is True
        assert error == ""
        motor_test_model.flight_controller.stop_all_motors.assert_called_once()


class TestMotorTestDataModelDiagramAndSettings:
    """Test motor diagram and settings management."""

    @patch.object(ProgramSettings, "motor_diagram_filepath")
    def test_user_can_get_motor_diagram_path(self, mock_filepath, motor_test_model) -> None:
        """
        User can retrieve the file path for motor diagram display.

        GIVEN: A configured frame type with available diagram
        WHEN: User requests motor diagram path
        THEN: Should return correct file path
        """
        # Arrange: Mock diagram path
        mock_filepath.return_value = "/path/to/motor_diagram.svg"

        # Act: Get diagram path
        path = motor_test_model.get_motor_diagram_path()

        # Assert: Correct path returned
        assert path == "/path/to/motor_diagram.svg"
        mock_filepath.assert_called_once_with(1, 1)

    @patch.object(ProgramSettings, "motor_diagram_exists")
    def test_user_can_check_if_motor_diagram_exists(self, mock_exists, motor_test_model) -> None:
        """
        User can verify if motor diagram is available for current frame.

        GIVEN: A configured frame type
        WHEN: User checks if diagram exists
        THEN: Should return availability status
        """
        # Arrange: Mock diagram existence
        mock_exists.return_value = True

        # Act: Check diagram existence
        exists = motor_test_model.motor_diagram_exists()

        # Assert: Diagram exists
        assert exists is True
        mock_exists.assert_called_once_with(1, 1)

    @patch.object(ProgramSettings, "get_motor_test_duration")
    def test_user_can_get_test_duration_setting(self, mock_get_duration, motor_test_model) -> None:
        """
        User can retrieve current motor test duration setting.

        GIVEN: Saved test duration preference
        WHEN: User requests test duration
        THEN: Should return saved duration value
        """
        # Arrange: Mock duration setting
        mock_get_duration.return_value = 3.0

        # Act: Get test duration
        duration = motor_test_model.get_test_duration()

        # Assert: Correct duration returned
        assert duration == 3.0
        mock_get_duration.assert_called_once()

    @patch.object(ProgramSettings, "set_motor_test_duration")
    def test_user_can_set_test_duration_setting(self, mock_set_duration, motor_test_model) -> None:
        """
        User can save motor test duration preference.

        GIVEN: A new test duration preference
        WHEN: User sets test duration
        THEN: Setting should be saved successfully
        """
        # Arrange: Mock successful save
        mock_set_duration.return_value = None

        # Act: Set test duration
        success = motor_test_model.set_test_duration(5.0)

        # Assert: Duration saved successfully
        assert success is True
        mock_set_duration.assert_called_once_with(5.0)

    @patch.object(ProgramSettings, "get_motor_test_throttle_pct")
    def test_user_can_get_throttle_percentage_setting(self, mock_get_throttle, motor_test_model) -> None:
        """
        User can retrieve current throttle percentage setting.

        GIVEN: Saved throttle percentage preference
        WHEN: User requests throttle percentage
        THEN: Should return saved percentage value
        """
        # Arrange: Mock throttle setting
        mock_get_throttle.return_value = 15

        # Act: Get throttle percentage
        throttle = motor_test_model.get_test_throttle_pct()

        # Assert: Correct percentage returned
        assert throttle == 15
        mock_get_throttle.assert_called_once()

    @patch.object(ProgramSettings, "set_motor_test_throttle_pct")
    def test_user_can_set_throttle_percentage_setting(self, mock_set_throttle, motor_test_model) -> None:
        """
        User can save throttle percentage preference.

        GIVEN: A new throttle percentage preference
        WHEN: User sets throttle percentage
        THEN: Setting should be saved successfully
        """
        # Arrange: Mock successful save
        mock_set_throttle.return_value = None

        # Act: Set throttle percentage
        success = motor_test_model.set_test_throttle_pct(20)

        # Assert: Percentage saved successfully
        assert success is True
        mock_set_throttle.assert_called_once_with(20)


class TestMotorTestDataModelFrameOptions:
    """Test frame configuration options and utilities."""

    def test_user_can_get_available_frame_options(self, motor_test_model) -> None:
        """
        User can retrieve all available frame class and type options.

        GIVEN: Motor test model with frame configuration support
        WHEN: User requests available frame options
        THEN: Should return complete list of classes and types
        """
        # Arrange: No special setup needed

        # Act: Get frame options
        options = motor_test_model.get_frame_options()

        # Assert: Complete options returned
        assert "classes" in options
        assert "types" in options
        assert 1 in options["classes"]  # Quad
        assert 2 in options["classes"]  # Hexa
        assert 0 in options["types"]  # Plus
        assert 1 in options["types"]  # X

    def test_user_can_refresh_connection_status_when_connected(self, motor_test_model) -> None:
        """
        User can refresh connection status and update configuration when connected.

        GIVEN: A connected flight controller
        WHEN: User refreshes connection status
        THEN: Should return True and update frame configuration
        """
        # Arrange: Connected flight controller in fixture

        # Act: Refresh connection status
        is_connected = motor_test_model.refresh_connection_status()

        # Assert: Connection refreshed successfully
        assert is_connected is True
        # Frame configuration should be updated (called during refresh)
        assert motor_test_model.flight_controller.get_frame_info.call_count >= 1

    def test_connection_status_refresh_fails_when_disconnected(self, motor_test_model) -> None:
        """
        Connection status refresh fails when flight controller is disconnected.

        GIVEN: A disconnected flight controller
        WHEN: User refreshes connection status
        THEN: Should return False
        """
        # Arrange: Disconnect flight controller
        motor_test_model.flight_controller.master = None

        # Act: Refresh connection status
        is_connected = motor_test_model.refresh_connection_status()

        # Assert: Connection refresh failed
        assert is_connected is False


class TestMotorTestDataModelEdgeCases:
    """Test edge cases and error scenarios."""

    def test_model_handles_flight_controller_communication_errors_gracefully(self, motor_test_model) -> None:
        """
        Model handles flight controller communication errors gracefully.

        GIVEN: A flight controller that raises communication errors
        WHEN: User performs operations that trigger communication
        THEN: Should handle errors gracefully with appropriate messages
        """
        # Arrange: Configure communication error
        motor_test_model.flight_controller.set_param.side_effect = Exception("Communication timeout")

        # Act: Attempt parameter setting
        success, error = motor_test_model.set_parameter("MOT_SPIN_ARM", 0.12)

        # Assert: Error handled gracefully
        assert success is False
        assert "Communication timeout" in error

    def test_model_handles_missing_parameters_gracefully(self, motor_test_model) -> None:
        """
        Model handles missing parameters gracefully.

        GIVEN: A flight controller missing expected parameters
        WHEN: User requests parameter values
        THEN: Should return appropriate default values
        """
        # Arrange: Remove parameter from FC
        motor_test_model.flight_controller.fc_parameters.pop("MOT_SPIN_ARM", None)

        # Act: Get missing parameter
        value = motor_test_model.get_parameter("MOT_SPIN_ARM")

        # Assert: Missing parameter handled gracefully
        assert value is None

    def test_voltage_thresholds_return_nan_when_disconnected(self, motor_test_model) -> None:
        """
        Voltage thresholds return NaN values when flight controller is disconnected.

        GIVEN: A disconnected flight controller
        WHEN: User requests voltage thresholds
        THEN: Should return NaN values
        """
        # Arrange: Disconnect flight controller
        motor_test_model.flight_controller.master = None
        motor_test_model.flight_controller.fc_parameters = None

        # Act: Get voltage thresholds
        min_voltage, max_voltage = motor_test_model.get_voltage_thresholds()

        # Assert: NaN values returned
        assert str(min_voltage) == "nan"
        assert str(max_voltage) == "nan"


class TestErrorHandlingAndEdgeCases:
    """Test error handling scenarios and edge cases to increase coverage."""

    def test_frame_configuration_update_exception_handling(self, motor_test_model) -> None:
        """
        Frame configuration update handles exceptions gracefully.

        GIVEN: A motor test model with frame configuration
        WHEN: An exception occurs during frame configuration update
        THEN: The exception should be caught and re-raised with proper logging
        """
        with (
            # Arrange: Mock an exception during frame configuration
            patch.object(motor_test_model, "_update_frame_configuration", side_effect=Exception("Test exception")),
            # Act & Assert: Exception should be caught and re-raised
            pytest.raises(Exception, match="Test exception"),
        ):
            motor_test_model(
                flight_controller=motor_test_model.flight_controller,
                filesystem=motor_test_model.filesystem,
                settings=motor_test_model.settings,
            )

    def test_battery_monitoring_disabled_check(self, motor_test_model) -> None:
        """
        Battery monitoring check returns False when FC connection is missing.

        GIVEN: A motor test model with no flight controller connection
        WHEN: Checking if battery monitoring is enabled
        THEN: Should return False with appropriate warning
        """
        # Arrange: Disconnect flight controller
        motor_test_model.flight_controller.master = None
        motor_test_model.flight_controller.fc_parameters = None

        # Act: Check battery monitoring
        result = motor_test_model.is_battery_monitoring_enabled()

        # Assert: Returns False when disconnected
        assert result is False

    def test_battery_status_when_monitoring_disabled(self, motor_test_model) -> None:
        """
        Battery status returns None when monitoring is disabled.

        GIVEN: A motor test model with battery monitoring disabled
        WHEN: Getting battery status
        THEN: Should return None
        """
        # Arrange: Disable battery monitoring
        motor_test_model.flight_controller.is_battery_monitoring_enabled.return_value = False

        # Act: Get battery status
        result = motor_test_model.get_battery_status()

        # Assert: Returns None when monitoring disabled
        assert result is None

    def test_battery_status_logs_warning_when_fc_disconnected(self, motor_test_model) -> None:
        """
        Battery status logs a warning when the flight controller is disconnected.

        GIVEN: A motor test model with battery monitoring enabled
        WHEN: The flight controller is disconnected and battery status is requested
        THEN: A warning should be logged and the status should be None
        """
        # Arrange: Enable monitoring but disconnect FC
        motor_test_model.flight_controller.is_battery_monitoring_enabled.return_value = True
        motor_test_model.flight_controller.master = None

        # Act
        with patch("ardupilot_methodic_configurator.data_model_motor_test.logging_warning") as mock_warning:
            result = motor_test_model.get_battery_status()

            # Assert
            assert result is None
            mock_warning.assert_called_once_with("Flight controller not connected, cannot get battery status.")

    def test_battery_status_with_debug_logging(self, motor_test_model) -> None:
        """
        Battery status logs debug message when error occurs.

        GIVEN: A motor test model with battery monitoring enabled
        WHEN: Battery status returns error message
        THEN: Should log debug message and return None
        """
        # Arrange: Configure battery status to return error
        motor_test_model.flight_controller.is_battery_monitoring_enabled.return_value = True
        motor_test_model.flight_controller.get_battery_status.return_value = (None, "Battery error")

        # Act: Get battery status
        result = motor_test_model.get_battery_status()

        # Assert: Returns None when error occurs
        assert result is None

    def test_safety_check_with_no_battery_data(self, motor_test_model) -> None:
        """
        Safety check returns disabled when no battery data available.

        GIVEN: A motor test model with battery monitoring but no data
        WHEN: Getting safety status
        THEN: Should return disabled status
        """
        # Arrange: Enable monitoring but return no battery data
        motor_test_model.flight_controller.is_battery_monitoring_enabled.return_value = True
        motor_test_model.flight_controller.get_battery_status.return_value = (None, "")

        # Act: Get voltage status
        result = motor_test_model.get_voltage_status()

        # Assert: Returns unavailable when no battery data
        assert result == "unavailable"

    def test_motor_test_with_unsafe_conditions(self, motor_test_model) -> None:
        """
        Motor test fails when safety conditions are not met.

        GIVEN: A motor test model with unsafe conditions
        WHEN: Attempting to test all motors
        THEN: Should fail with safety reason
        """
        # Arrange: Make conditions unsafe
        with patch.object(motor_test_model, "is_motor_test_safe", return_value=(False, "Unsafe voltage")):
            # Act: Attempt motor test
            success, reason = motor_test_model.test_all_motors(50, 3)

            # Assert: Test fails due to safety
            assert success is False
            assert reason == "Unsafe voltage"

    def test_sequential_motor_test_with_unsafe_conditions(self, motor_test_model) -> None:
        """
        Sequential motor test fails when safety conditions are not met.

        GIVEN: A motor test model with unsafe conditions
        WHEN: Attempting to test motors in sequence
        THEN: Should fail with safety reason
        """
        # Arrange: Make conditions unsafe
        with patch.object(motor_test_model, "is_motor_test_safe", return_value=(False, "Battery too low")):
            # Act: Attempt sequential motor test
            success, reason = motor_test_model.test_motors_in_sequence(30, 2)

            # Assert: Test fails due to safety
            assert success is False
            assert reason == "Battery too low"

    def test_set_test_duration_exception_handling(self, motor_test_model) -> None:
        """
        Set test duration handles exceptions gracefully.

        GIVEN: A motor test model
        WHEN: An exception occurs while setting test duration
        THEN: Should return False and log error
        """
        # Arrange: Mock exception in ProgramSettings
        with patch(
            "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.set_motor_test_duration",
            side_effect=Exception("Save error"),
        ):
            # Act: Attempt to set duration
            result = motor_test_model.set_test_duration(5)

            # Assert: Returns False on exception
            assert result is False

    def test_set_test_throttle_exception_handling(self, motor_test_model) -> None:
        """
        Set test throttle handles exceptions gracefully.

        GIVEN: A motor test model
        WHEN: An exception occurs while setting test throttle
        THEN: Should return False and log error
        """
        # Arrange: Mock exception in ProgramSettings
        with patch(
            "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.set_motor_test_throttle_pct",
            side_effect=Exception("Save error"),
        ):
            # Act: Attempt to set throttle
            result = motor_test_model.set_test_throttle_pct(75)

            # Assert: Returns False on exception
            assert result is False

    def test_update_frame_configuration_class_parameter_failure(self, motor_test_model) -> None:
        """
        Frame configuration update fails when FRAME_CLASS parameter setting fails.

        GIVEN: A motor test model
        WHEN: Setting FRAME_CLASS parameter fails
        THEN: Should return failure with appropriate error message
        """
        # Arrange: Mock parameter setting to fail for FRAME_CLASS
        with patch.object(motor_test_model, "set_parameter") as mock_set_param:
            mock_set_param.side_effect = [
                (False, "Failed to set FRAME_CLASS"),  # First call fails
                (True, ""),  # Second call would succeed but shouldn't be reached
            ]

            # Act: Attempt frame configuration update
            success, error = motor_test_model.update_frame_configuration(2, 0)

            # Assert: Returns failure for FRAME_CLASS error
            assert success is False
            assert error == "Failed to set FRAME_CLASS"

    def test_update_frame_configuration_type_parameter_failure(self, motor_test_model) -> None:
        """
        Frame configuration update fails when FRAME_TYPE parameter setting fails.

        GIVEN: A motor test model
        WHEN: Setting FRAME_TYPE parameter fails
        THEN: Should return failure with appropriate error message
        """
        # Arrange: Mock parameter setting to fail for FRAME_TYPE
        with patch.object(motor_test_model, "set_parameter") as mock_set_param:
            mock_set_param.side_effect = [
                (True, ""),  # FRAME_CLASS succeeds
                (False, "Failed to set FRAME_TYPE"),  # FRAME_TYPE fails
            ]

            # Act: Attempt frame configuration update
            success, error = motor_test_model.update_frame_configuration(2, 0)

            # Assert: Returns failure for FRAME_TYPE error
            assert success is False
            assert error == "Failed to set FRAME_TYPE"

    def test_update_frame_configuration_exception_during_update(self, motor_test_model) -> None:
        """
        Frame configuration update handles exceptions during the update process.

        GIVEN: A motor test model
        WHEN: An exception occurs during motor count calculation
        THEN: Should return failure with error message
        """
        # Arrange: Mock parameter setting to succeed but motor count calculation to fail
        with (
            patch.object(motor_test_model, "set_parameter", return_value=(True, "")),
            patch.object(
                motor_test_model.flight_controller,
                "get_motor_count_from_frame",
                side_effect=Exception("Motor count calculation failed"),
            ),
        ):
            # Act: Attempt frame configuration update
            success, error = motor_test_model.update_frame_configuration(2, 0)

            # Assert: Returns failure with exception message
            assert success is False
            assert "Failed to update frame configuration: Motor count calculation failed" in error

    def test_refresh_connection_status_exception_handling(self, motor_test_model) -> None:
        """
        Refresh connection status handles exceptions gracefully.

        GIVEN: A motor test model
        WHEN: An exception occurs during connection status refresh
        THEN: Should return False and log warning
        """
        # Arrange: Mock exception during frame configuration update
        with patch.object(motor_test_model, "_update_frame_configuration", side_effect=Exception("Connection error")):
            # Act: Attempt to refresh connection status
            result = motor_test_model.refresh_connection_status()

            # Assert: Returns False on exception
            assert result is False
