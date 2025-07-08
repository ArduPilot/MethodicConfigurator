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

# pylint: disable=too-many-lines,redefined-outer-name,protected-access,too-few-public-methods


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
    filesystem = MagicMock()

    # Configure frame options for testing
    filesystem.get_frame_options.return_value = {
        "classes": {
            1: "QUAD",
            2: "HEXA",
            3: "OCTA",
            4: "OCTAQUAD",
            5: "Y6",
            7: "TRI",
        },
        "types": {
            0: "PLUS",
            1: "X",
            2: "V",
            3: "H",
        },
    }

    # Configure doc_dict for get_frame_options method
    filesystem.doc_dict = {
        "FRAME_CLASS": {
            "values": {
                "1": "QUAD",
                "2": "HEXA",
                "3": "OCTA",
                "4": "OCTAQUAD",
                "5": "Y6",
                "7": "TRI",
            }
        },
        "FRAME_TYPE": {
            "values": {
                "0": "QUAD: PLUS",
                "1": "QUAD: X",
                "2": "HEXA: PLUS",
                "3": "HEXA: X",
                "10": "OCTA: PLUS",
                "11": "OCTA: X",
            }
        },
    }

    return filesystem


@pytest.fixture
def mock_settings() -> MagicMock:
    """Fixture providing mock program settings."""
    return MagicMock(spec=ProgramSettings)


@pytest.fixture
def motor_test_model(mock_flight_controller, mock_filesystem, mock_motor_data_json) -> MotorTestDataModel:
    """Fixture providing a properly configured motor test data model for behavior testing."""
    with patch("ardupilot_methodic_configurator.data_model_motor_test.FilesystemJSONWithSchema") as mock_json_loader_class:
        # Configure the mock loader instance
        mock_loader_instance = MagicMock()
        mock_loader_instance.load_json_data.return_value = mock_motor_data_json
        mock_loader_instance.data = mock_motor_data_json
        mock_json_loader_class.return_value = mock_loader_instance

        # Create the model - it will use our mocked JSON data
        return MotorTestDataModel(
            flight_controller=mock_flight_controller,
            filesystem=mock_filesystem,
        )


@pytest.fixture
def disconnected_flight_controller() -> MagicMock:
    """Fixture providing a disconnected flight controller for testing error scenarios."""
    fc = MagicMock(spec=FlightController)
    fc.master = None  # Simulate disconnected state
    fc.fc_parameters = None
    return fc


@pytest.fixture
def mock_motor_data_json() -> dict:
    """Fixture providing realistic motor configuration JSON data for testing."""
    return {
        "Version": "AP_Motors library test ver 1.2",
        "layouts": [
            {
                "Class": 1,
                "ClassName": "QUAD",
                "Type": 0,
                "TypeName": "PLUS",
                "motors": [
                    {"Number": 1, "TestOrder": 2, "Rotation": "CCW", "Roll": -0.5, "Pitch": 0.0},
                    {"Number": 2, "TestOrder": 4, "Rotation": "CCW", "Roll": 0.5, "Pitch": 0.0},
                    {"Number": 3, "TestOrder": 1, "Rotation": "CW", "Roll": 0.0, "Pitch": 0.5},
                    {"Number": 4, "TestOrder": 3, "Rotation": "CW", "Roll": 0.0, "Pitch": -0.5},
                ],
            },
            {
                "Class": 1,
                "ClassName": "QUAD",
                "Type": 1,
                "TypeName": "X",
                "motors": [
                    {"Number": 1, "TestOrder": 1, "Rotation": "CCW", "Roll": -0.5, "Pitch": 0.5},
                    {"Number": 2, "TestOrder": 2, "Rotation": "CW", "Roll": 0.5, "Pitch": 0.5},
                    {"Number": 3, "TestOrder": 3, "Rotation": "CW", "Roll": -0.5, "Pitch": -0.5},
                    {"Number": 4, "TestOrder": 4, "Rotation": "CCW", "Roll": 0.5, "Pitch": -0.5},
                ],
            },
            {
                "Class": 2,
                "ClassName": "HEXA",
                "Type": 1,
                "TypeName": "X",
                "motors": [
                    {"Number": 1, "TestOrder": 1, "Rotation": "CW", "Roll": -0.5, "Pitch": 0.866},
                    {"Number": 2, "TestOrder": 2, "Rotation": "CCW", "Roll": 0.5, "Pitch": 0.866},
                    {"Number": 3, "TestOrder": 3, "Rotation": "CW", "Roll": 1.0, "Pitch": 0.0},
                    {"Number": 4, "TestOrder": 4, "Rotation": "CCW", "Roll": 0.5, "Pitch": -0.866},
                    {"Number": 5, "TestOrder": 5, "Rotation": "CW", "Roll": -0.5, "Pitch": -0.866},
                    {"Number": 6, "TestOrder": 6, "Rotation": "CCW", "Roll": -1.0, "Pitch": 0.0},
                ],
            },
        ],
    }


@pytest.fixture
def motor_test_model_with_json_data(mock_flight_controller, mock_filesystem, mock_motor_data_json) -> MotorTestDataModel:
    """Fixture providing a motor test model with mocked JSON data loading."""
    with patch("ardupilot_methodic_configurator.data_model_motor_test.FilesystemJSONWithSchema") as mock_json_loader_class:
        # Configure the mock loader instance
        mock_loader_instance = MagicMock()
        mock_loader_instance.load_json_data.return_value = mock_motor_data_json
        mock_loader_instance.data = mock_motor_data_json
        mock_json_loader_class.return_value = mock_loader_instance

        # Create the model - it will use our mocked JSON data
        return MotorTestDataModel(
            flight_controller=mock_flight_controller,
            filesystem=mock_filesystem,
        )


@pytest.fixture
def motor_test_model_with_empty_json_data(mock_flight_controller, mock_filesystem) -> MotorTestDataModel:
    """Fixture providing a motor test model with empty/failed JSON data loading."""
    with patch("ardupilot_methodic_configurator.data_model_motor_test.FilesystemJSONWithSchema") as mock_json_loader_class:
        # Configure the mock loader instance to return empty data
        mock_loader_instance = MagicMock()
        mock_loader_instance.load_json_data.return_value = {}
        mock_loader_instance.data = {}
        mock_json_loader_class.return_value = mock_loader_instance

        # For empty JSON data, we need to bypass the frame configuration validation
        with patch("ardupilot_methodic_configurator.data_model_motor_test.MotorTestDataModel._update_frame_configuration"):
            model = MotorTestDataModel(flight_controller=mock_flight_controller, filesystem=mock_filesystem)
            # Manually set the attributes since _update_frame_configuration was bypassed
            model._frame_class = 1
            model._frame_type = 1
            model._motor_count = 0
            model._frame_layout = {}
            return model


@pytest.fixture
def motor_test_model_with_corrupted_json_data(mock_flight_controller, mock_filesystem) -> MotorTestDataModel:
    """Fixture providing a motor test model with corrupted/invalid JSON data."""
    with patch("ardupilot_methodic_configurator.data_model_motor_test.FilesystemJSONWithSchema") as mock_json_loader_class:
        # Configure the mock loader instance to return invalid data
        mock_loader_instance = MagicMock()
        mock_loader_instance.load_json_data.return_value = {"invalid": "structure"}
        mock_loader_instance.data = {"invalid": "structure"}
        mock_json_loader_class.return_value = mock_loader_instance

        # For corrupted JSON data, we need to bypass the frame configuration validation
        with patch("ardupilot_methodic_configurator.data_model_motor_test.MotorTestDataModel._update_frame_configuration"):
            model = MotorTestDataModel(flight_controller=mock_flight_controller, filesystem=mock_filesystem)
            # Manually set the attributes since _update_frame_configuration was bypassed
            model._frame_class = 1
            model._frame_type = 1
            model._motor_count = 0
            model._frame_layout = {}
            return model


# ==================== INITIALIZATION TESTS ====================


class TestMotorTestDataModelInitialization:
    """Test motor test data model initialization and configuration."""

    def test_user_can_initialize_model_with_connected_flight_controller(self, mock_flight_controller, mock_filesystem) -> None:
        """
        User can successfully initialize motor test model with connected flight controller.

        GIVEN: A connected flight controller with valid frame configuration
        WHEN: User initializes the motor test data model
        THEN: Model should be configured with correct frame settings
        """
        # Arrange: Flight controller already configured in fixture

        # Act: Initialize the model
        model = MotorTestDataModel(flight_controller=mock_flight_controller, filesystem=mock_filesystem)

        # Assert: Frame configuration loaded correctly
        assert model.frame_class == 1
        assert model.frame_type == 1
        assert model.get_motor_count() == 4
        mock_flight_controller.get_frame_info.assert_called_once()

    def test_model_initialization_fails_with_disconnected_flight_controller(
        self, disconnected_flight_controller, mock_filesystem
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
            MotorTestDataModel(flight_controller=disconnected_flight_controller, filesystem=mock_filesystem)

    def test_frame_configuration_update_failure_in_init(self) -> None:
        """
        Model initialization handles frame configuration update failures gracefully.

        GIVEN: A flight controller with connection issues during frame configuration
        WHEN: User attempts to initialize the motor test data model
        THEN: Should raise RuntimeError with descriptive error message
        """
        # Arrange: Mock flight controller that fails during frame configuration
        mock_fc = MagicMock(spec=FlightController)
        mock_fc.master = MagicMock()  # Simulate connected state
        mock_fc.fc_parameters = {"FRAME_CLASS": 1}  # Valid parameters dict
        mock_fc.get_frame_info.side_effect = Exception("Frame info error")

        mock_filesystem = MagicMock(spec=LocalFilesystem)

        # Act & Assert: Initialization should fail with descriptive error
        with pytest.raises(Exception, match="Frame info error"):
            MotorTestDataModel(flight_controller=mock_fc, filesystem=mock_filesystem)

    def test_frame_configuration_update_failure_in_init_raises_exception(self) -> None:
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

        # Act & Assert: Exception should be raised
        with pytest.raises(Exception, match="Frame info error"):
            MotorTestDataModel(mock_fc, mock_filesystem)


class TestMotorTestDataModelFrameConfiguration:
    """Test frame configuration management and motor counting."""

    def test_user_can_get_motor_labels_for_current_frame(self, motor_test_model) -> None:
        """
        User can retrieve motor labels for the current frame configuration.

        GIVEN: Motor test model with 4-motor frame configuration
        WHEN: User requests motor labels
        THEN: Should return correct alphabetic labels (A, B, C, D)
        """
        # Arrange: Motor count is configured in fixture (4 motors)

        # Act: Get motor labels
        labels = motor_test_model.get_motor_labels()

        # Assert: Correct labels returned
        assert labels == ["A", "B", "C", "D"]
        assert len(labels) == 4

    def test_user_can_get_motor_numbers_for_current_frame(self, motor_test_model) -> None:
        """
        User can retrieve motor numbers for the current frame configuration.

        GIVEN: Motor test model with 4-motor frame configuration (QUAD X)
        WHEN: User requests motor numbers
        THEN: Should return motor numbers in test order for QUAD X frame
        """
        # Arrange: Motor count is configured in fixture (4 motors, QUAD X)

        # Act: Get motor numbers (in test order)
        numbers = motor_test_model.get_motor_numbers()

        # Assert: Correct numbers returned in test order for QUAD X
        # Based on mock_motor_data_json: QUAD X has TestOrder [1,2,3,4] for Motors [1,2,3,4]
        assert numbers == [1, 2, 3, 4]
        assert len(numbers) == 4

    def test_user_can_update_frame_configuration_successfully(self, motor_test_model) -> None:
        """
        User can successfully update frame configuration on flight controller.

        GIVEN: Motor test model with connected flight controller
        WHEN: User updates frame class and type
        THEN: Parameters should be uploaded and internal state updated
        """
        # Arrange: Configure successful parameter setting
        with patch.object(motor_test_model, "set_parameter", return_value=(True, "")):
            # Act: Update frame configuration
            success, error_msg = motor_test_model.update_frame_configuration(2, 1)  # Hexa X

            # Assert: Update successful
            assert success is True
            assert error_msg == ""
            assert motor_test_model.frame_class == 2
            assert motor_test_model.frame_type == 1
            assert motor_test_model.get_motor_count() == 6  # HEXA X has 6 motors

    def test_user_can_update_frame_configuration_and_motor_count(self, motor_test_model) -> None:
        """
        User can successfully update frame configuration and motor count.

        GIVEN: A motor test model with current frame configuration
        WHEN: User updates frame class and type
        THEN: Frame should be updated and motor count recalculated
        """
        # Arrange: Mock set_parameter to return success
        with patch.object(motor_test_model, "set_parameter", return_value=(True, "")):
            # Act: Update frame configuration
            success, error = motor_test_model.update_frame_configuration(frame_class=2, frame_type=1)

            # Assert: Configuration updated successfully
            assert success is True
            assert error == ""
            assert motor_test_model.frame_class == 2
            assert motor_test_model.frame_type == 1
            assert motor_test_model.get_motor_count() == 6  # HEXA X has 6 motors

    def test_frame_configuration_update_fails_with_disconnected_controller(
        self, disconnected_flight_controller, mock_filesystem
    ) -> None:
        """
        Frame configuration update fails gracefully when flight controller is disconnected.

        GIVEN: A disconnected flight controller
        WHEN: User attempts to update frame configuration
        THEN: Should return failure with descriptive error message
        """
        # Arrange: Create model with disconnected FC (this will raise during init)
        with pytest.raises(RuntimeError):
            MotorTestDataModel(flight_controller=disconnected_flight_controller, filesystem=mock_filesystem)

    def test_frame_configuration_update_fails_with_disconnected_controller2(
        self, disconnected_flight_controller, mock_filesystem
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
            model = MotorTestDataModel(flight_controller=disconnected_flight_controller, filesystem=mock_filesystem)
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
        User can check if battery monitoring is enabled.

        GIVEN: Motor test model with battery monitoring enabled
        WHEN: User checks battery monitoring status
        THEN: Should return True
        """
        # Arrange: Battery monitoring configured in fixture

        # Act: Check battery monitoring status
        is_enabled = motor_test_model.is_battery_monitoring_enabled()

        # Assert: Battery monitoring is enabled
        assert is_enabled is True

    def test_user_can_get_current_battery_status(self, motor_test_model) -> None:
        """
        User can retrieve current battery voltage and current readings.

        GIVEN: Motor test model with battery monitoring enabled
        WHEN: User requests battery status
        THEN: Should return valid voltage and current values
        """
        # Arrange: Battery status configured in fixture

        # Act: Get battery status
        battery_status = motor_test_model.get_battery_status()

        # Assert: Valid battery status returned
        assert battery_status is not None
        voltage, current = battery_status
        assert voltage == 12.4  # From fixture
        assert current == 2.1  # From fixture

    def test_user_gets_no_battery_status_when_monitoring_disabled(self, motor_test_model) -> None:
        """
        User gets None when battery monitoring is disabled.

        GIVEN: Motor test model with battery monitoring disabled
        WHEN: User requests battery status
        THEN: Should return None
        """
        # Arrange: Disable battery monitoring
        motor_test_model.flight_controller.is_battery_monitoring_enabled.return_value = False

        # Act: Get battery status
        battery_status = motor_test_model.get_battery_status()

        # Assert: No battery status available
        assert battery_status is None

    def test_user_can_get_voltage_thresholds_for_safety(self, motor_test_model) -> None:
        """
        User can retrieve voltage thresholds for motor testing safety.

        GIVEN: Motor test model with connected flight controller
        WHEN: User requests voltage thresholds
        THEN: Should return valid min and max voltage values
        """
        # Arrange: Voltage thresholds configured in fixture

        # Act: Get voltage thresholds
        min_voltage, max_voltage = motor_test_model.get_voltage_thresholds()

        # Assert: Valid thresholds returned
        assert min_voltage == 11.0  # From fixture
        assert max_voltage == 16.8  # From fixture

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
        Motor testing is allowed when all safety conditions are met.

        GIVEN: Motor test model with connected flight controller and good battery
        WHEN: User checks if motor testing is safe
        THEN: Should return True with no safety warnings
        """
        # Arrange: Good conditions configured in fixture

        # Act: Check motor testing safety
        is_safe, reason = motor_test_model.is_motor_test_safe()

        # Assert: Motor testing is safe
        assert is_safe is True
        assert reason == ""

    def test_motor_testing_unsafe_with_disconnected_controller(self, motor_test_model) -> None:
        """
        Motor testing is unsafe when flight controller is disconnected.

        GIVEN: Motor test model with disconnected flight controller
        WHEN: User checks if motor testing is safe
        THEN: Should return False with appropriate error message
        """
        # Arrange: Disconnect flight controller
        motor_test_model.flight_controller.master = None

        # Act: Check motor testing safety
        is_safe, reason = motor_test_model.is_motor_test_safe()

        # Assert: Motor testing is unsafe
        assert is_safe is False
        assert "not connected" in reason.lower()

    def test_motor_testing_unsafe_with_no_battery_monitoring(self, motor_test_model) -> None:
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
        assert "Flight controller not connected" in reason

    def test_motor_testing_safe_with_battery_monitoring_disabled(self, motor_test_model) -> None:
        """
        Motor testing is safe when battery monitoring is disabled.

        GIVEN: A flight controller with battery monitoring disabled
        WHEN: User checks if motor testing is safe
        THEN: Should return True with a warning about disabled monitoring
        """
        # Arrange: Disable battery monitoring
        motor_test_model.flight_controller.is_battery_monitoring_enabled.return_value = False

        # Act: Check motor test safety
        is_safe, reason = motor_test_model.is_motor_test_safe()

        # Assert: Motor testing is safe even without battery monitoring
        assert is_safe is True
        assert "Battery monitoring disabled" in reason

    def test_motor_testing_unsafe_with_low_voltage(self, motor_test_model) -> None:
        """
        Motor testing is unsafe when battery voltage is below minimum threshold.

        GIVEN: A battery with voltage below the minimum threshold
        WHEN: User checks if motor testing is safe
        THEN: Should return False with low voltage warning
        """
        # Arrange: Set voltage below minimum threshold
        motor_test_model.flight_controller.get_battery_status.return_value = ((10.5, 2.1), "")
        min_voltage, max_voltage = motor_test_model.get_voltage_thresholds()

        # Act: Check motor test safety
        is_safe, reason = motor_test_model.is_motor_test_safe()

        # Assert: Motor testing is unsafe due to low voltage
        assert is_safe is False
        assert f"Battery voltage 10.5V is outside safe range ({min_voltage}V - {max_voltage}V)" in reason

    def test_motor_testing_unsafe_with_high_voltage(self, motor_test_model) -> None:
        """
        Motor testing is unsafe when battery voltage is above maximum threshold.

        GIVEN: A battery with voltage above the maximum threshold
        WHEN: User checks if motor testing is safe
        THEN: Should return False with high voltage warning
        """
        # Arrange: Set voltage above maximum threshold
        motor_test_model.flight_controller.get_battery_status.return_value = ((17.0, 2.1), "")
        min_voltage, max_voltage = motor_test_model.get_voltage_thresholds()

        # Act: Check motor test safety
        is_safe, reason = motor_test_model.is_motor_test_safe()

        # Assert: Motor testing is unsafe due to high voltage
        assert is_safe is False
        assert f"Battery voltage 17.0V is outside safe range ({min_voltage}V - {max_voltage}V)" in reason


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
        User can test an individual motor when safety conditions are met.

        GIVEN: Motor test model with safe conditions
        WHEN: User tests a specific motor with valid parameters
        THEN: Motor test should be executed successfully
        """
        # Arrange: Safe conditions configured in fixture

        # Act: Test motor 1 at 10% throttle for 2 seconds
        success, error_msg = motor_test_model.test_motor(1, 10, 2)

        # Assert: Motor test successful
        assert success is True
        assert error_msg == ""
        motor_test_model.flight_controller.test_motor.assert_called_once_with(1, 10, 2)

    def test_motor_test_fails_with_invalid_motor_number(self, motor_test_model) -> None:
        """
        Motor test fails when invalid motor number is specified.

        GIVEN: Motor test model with 4-motor configuration
        WHEN: User attempts to test motor 5 (out of range)
        THEN: Should return failure with descriptive error message
        """
        # Arrange: 4-motor configuration in fixture

        # Act: Attempt to test invalid motor number
        success, error_msg = motor_test_model.test_motor(5, 10, 2)

        # Assert: Test fails with appropriate error
        assert success is False
        assert "Invalid motor number" in error_msg
        assert "5" in error_msg
        assert "1-4" in error_msg

    def test_motor_test_fails_with_invalid_motor_number2(self, motor_test_model) -> None:
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
        THEN: Should return failure with safety
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
        motor_test_model.flight_controller.test_motors_in_sequence.assert_called_once_with(4, 10, 2)

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
    def test_user_can_get_motor_diagram_path(self, mock_filepath: MagicMock, motor_test_model: MotorTestDataModel) -> None:
        """
        User can retrieve the file path for motor diagram display.

        GIVEN: A configured frame type with available diagram
        WHEN: User requests motor diagram path
        THEN: Should return correct file path
        """
        # Arrange: Mock diagram path
        mock_filepath.return_value = ("/path/to/motor_diagram.svg", "")

        # Act: Get diagram path
        path = motor_test_model.get_motor_diagram_path()

        # Assert: Correct path returned
        assert path == ("/path/to/motor_diagram.svg", "")
        mock_filepath.assert_called_once_with(1, 1)

    @patch.object(ProgramSettings, "motor_diagram_exists")
    def test_user_can_check_if_motor_diagram_exists(
        self, mock_exists: MagicMock, motor_test_model: MotorTestDataModel
    ) -> None:
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


class TestMotorTestDataModelFrameOptions:
    """Test frame configuration options and utilities."""

    def test_user_can_get_available_frame_options(self, motor_test_model) -> None:
        """
        User can retrieve all available frame class and type options.

        GIVEN: Motor test model with frame configuration support
        WHEN: User requests available frame options
        THEN: Should return frame types organized by frame class
        """
        # Arrange: No special setup needed

        # Act: Get frame options
        options = motor_test_model.get_frame_options()

        # Assert: Frame types organized by frame class (based on mock motor data)
        assert "QUAD" in options
        assert "HEXA" in options
        # Note: OCTA not in mock motor data, so it won't be available
        assert 0 in options["QUAD"]  # PLUS
        assert 1 in options["QUAD"]  # X
        assert options["QUAD"][0] == "PLUS"
        assert options["QUAD"][1] == "X"
        assert 1 in options["HEXA"]  # X (only X is in mock data for HEXA)
        assert options["HEXA"][1] == "X"

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
            patch.object(MotorTestDataModel, "_update_frame_configuration", side_effect=Exception("Test exception")),
            # Act & Assert: Exception should be caught and re-raised
            pytest.raises(Exception, match="Test exception"),
        ):
            MotorTestDataModel(
                flight_controller=motor_test_model.flight_controller,
                filesystem=motor_test_model.filesystem,
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
            success, reason = motor_test_model.test_motors_in_sequence(throttle_percent=30, timeout_seconds=2)

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
        # Arrange: Mock exception in ProgramSettings.set_setting
        with patch(
            "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.set_setting",
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
        # Arrange: Mock exception in ProgramSettings.set_setting
        with patch(
            "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.set_setting",
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
        WHEN: An exception occurs during the update process
        THEN: Should return failure with error message
        """
        # Arrange: Mock an exception during the update process
        with patch.object(motor_test_model, "set_parameter") as mock_set_param:
            mock_set_param.side_effect = Exception("Internal error during parameter setting")

            # Act: Attempt frame configuration update
            success, error = motor_test_model.update_frame_configuration(2, 0)

            # Assert: Returns failure with exception message
            assert success is False
            assert "Failed to update frame configuration: Internal error during parameter setting" in error

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


class TestMotorTestDataModelMotorDirections:
    """Test motor direction retrieval from JSON data and fallback logic."""

    def test_user_can_get_motor_directions_from_valid_json_data(self, motor_test_model_with_json_data) -> None:
        """
        User can retrieve correct motor rotation directions from loaded JSON data.

        GIVEN: A motor test model with valid JSON motor layout data
        WHEN: User requests motor directions for a configured frame (QUAD X)
        THEN: Should return accurate rotation directions from JSON data
        """
        # Arrange: Model configured with Quad X frame (class=1, type=1) in fixture
        model = motor_test_model_with_json_data

        # Act: Get motor directions
        directions = model.get_motor_directions()

        # Assert: Correct directions returned from JSON data
        expected_directions = ["CCW", "CW", "CW", "CCW"]  # From mock JSON for QUAD X
        assert directions == expected_directions
        assert len(directions) == 4

    def test_user_can_get_motor_directions_for_quad_plus_frame(self, motor_test_model_with_json_data) -> None:
        """
        User can retrieve motor directions for QUAD PLUS frame configuration.

        GIVEN: A motor test model with JSON data and QUAD PLUS frame
        WHEN: User requests motor directions
        THEN: Should return correct directions for PLUS configuration
        """
        # Arrange: Update model to QUAD PLUS frame (class=1, type=0)
        model = motor_test_model_with_json_data
        model._frame_class = 1
        model._frame_type = 0
        model._motor_count = 4
        # Update the frame layout to match QUAD PLUS
        for layout in model._motor_data_loader.data["layouts"]:
            if layout["Class"] == 1 and layout["Type"] == 0:
                model._frame_layout = layout
                break

        # Act: Get motor directions
        directions = model.get_motor_directions()

        # Assert: Correct PLUS frame directions in test order
        expected_directions = ["CW", "CCW", "CW", "CCW"]  # Test order 1,2,3,4 from mock JSON for QUAD PLUS
        assert directions == expected_directions
        assert len(directions) == 4

    def test_user_can_get_motor_directions_for_hexa_frame(self, motor_test_model_with_json_data) -> None:
        """
        User can retrieve motor directions for hexacopter frame configuration.

        GIVEN: A motor test model with JSON data and HEXA frame
        WHEN: User requests motor directions
        THEN: Should return correct 6-motor directions
        """
        # Arrange: Update model to HEXA frame (class=2, type=1)
        model = motor_test_model_with_json_data
        model._frame_class = 2
        model._frame_type = 1
        model._motor_count = 6
        # Update the frame layout to match HEXA X
        for layout in model._motor_data_loader.data["layouts"]:
            if layout["Class"] == 2 and layout["Type"] == 1:
                model._frame_layout = layout
                break

        # Act: Get motor directions
        directions = model.get_motor_directions()

        # Assert: Correct HEXA frame directions
        expected_directions = ["CW", "CCW", "CW", "CCW", "CW", "CCW"]  # From mock JSON for HEXA X
        assert directions == expected_directions
        assert len(directions) == 6

    def test_user_gets_fallback_when_frame_not_found_in_json(self, motor_test_model_with_json_data) -> None:
        """
        User gets appropriate error when frame configuration not found in JSON.

        GIVEN: A motor test model with JSON data
        WHEN: User requests directions for unsupported frame configuration
        THEN: Should raise ValueError with appropriate error message
        """
        # Arrange: Configure unsupported frame (class=99, type=99)
        model = motor_test_model_with_json_data
        model._frame_class = 99
        model._frame_type = 99
        model._motor_count = 4
        model._frame_layout = {}  # No frame layout found

        # Act & Assert: Should raise ValueError
        with pytest.raises(ValueError, match="No Frame layout found"):
            model.get_motor_directions()

    def test_user_gets_fallback_when_json_data_empty(self, motor_test_model_with_empty_json_data) -> None:
        """
        User gets appropriate error when JSON data is empty or invalid.

        GIVEN: A motor test model with empty or failed JSON data loading
        WHEN: User requests motor directions
        THEN: Should raise ValueError with appropriate error message
        """
        # Arrange: Model with empty JSON data from fixture
        model = motor_test_model_with_empty_json_data
        model._frame_layout = {}  # No frame layout available

        # Act & Assert: Should raise ValueError
        with pytest.raises(ValueError, match="No Frame layout found"):
            model.get_motor_directions()

    def test_user_gets_fallback_when_json_data_corrupted(self, motor_test_model_with_corrupted_json_data) -> None:
        """
        User gets appropriate error when JSON data structure is invalid.

        GIVEN: A motor test model with corrupted JSON data structure
        WHEN: User requests motor directions
        THEN: Should raise ValueError with appropriate error message
        """
        # Arrange: Model with corrupted JSON data from fixture
        model = motor_test_model_with_corrupted_json_data

        # Act & Assert: Get motor directions should raise ValueError
        with pytest.raises(ValueError, match="No Frame layout found, not possible to generate motor test rotation order"):
            model.get_motor_directions()

    def test_motor_count_mismatch_handled_with_extension(self, motor_test_model_with_json_data) -> None:
        """
        System handles motor count mismatch by leaving missing positions empty.

        GIVEN: A motor test model where JSON has fewer motors than expected
        WHEN: User requests directions for frame needing more motors
        THEN: Should return directions with empty strings for missing motors
        """
        # Arrange: Configure frame with valid class/type then simulate motor count mismatch
        model = motor_test_model_with_json_data
        with patch.object(model, "set_parameter", return_value=(True, None)):
            model.update_frame_configuration(1, 1)  # Configure QUAD X frame (has 4 motors)

        # Manually increase motor count to simulate mismatch
        model._motor_count = 8  # Expect 8 motors but frame layout only has 4

        # Act: Get motor directions
        directions = model.get_motor_directions()

        # Assert: Directions list has correct length with empty strings for missing motors
        assert len(directions) == 8
        # First 4 from JSON, remaining 4 are empty strings
        expected_directions = ["CCW", "CW", "CW", "CCW", "", "", "", ""]
        assert directions == expected_directions

    def test_motor_count_mismatch_handled_with_truncation(self, motor_test_model_with_json_data) -> None:
        """
        System handles motor count mismatch by truncating directions appropriately.

        GIVEN: A motor test model where JSON has more motors than expected
        WHEN: User requests directions for frame needing fewer motors
        THEN: Should truncate directions to match expected count
        """
        # Arrange: Configure frame with valid class/type then simulate motor count mismatch
        model = motor_test_model_with_json_data
        with patch.object(model, "set_parameter", return_value=(True, None)):
            model.update_frame_configuration(2, 1)  # Configure HEXA frame (has 6 motors)

        # Manually decrease motor count to simulate mismatch
        model._motor_count = 4  # Expect only 4 motors but frame layout has 6

        # Act: Get motor directions
        directions = model.get_motor_directions()

        # Assert: Directions truncated to match motor count
        assert len(directions) == 4
        # Only first 4 directions from frame layout
        expected_directions = ["CW", "CCW", "CW", "CCW"]
        assert directions == expected_directions


class TestMotorTestDataModelJSONLoading:
    """Test JSON data loading, validation, and error handling."""

    def test_model_loads_json_data_successfully_on_initialization(self, mock_flight_controller, mock_filesystem) -> None:
        """
        Model successfully loads and validates JSON motor data during initialization.

        GIVEN: Valid AP_Motors_test.json file exists in application directory
        WHEN: User initializes the motor test data model with matching frame layout
        THEN: JSON data should be loaded and stored for later use
        """
        # Arrange: Mock successful JSON loading with matching frame layout
        mock_flight_controller.get_frame_info.return_value = (1, 1)  # QUAD_X frame

        with patch("ardupilot_methodic_configurator.data_model_motor_test.FilesystemJSONWithSchema") as mock_json_class:
            mock_loader = MagicMock()
            mock_loader.load_json_data.return_value = {
                "layouts": [
                    {
                        "Class": 1,
                        "Type": 1,
                        "motors": [
                            {"Number": 1, "TestOrder": 1, "Rotation": "CCW"},
                            {"Number": 2, "TestOrder": 2, "Rotation": "CW"},
                            {"Number": 3, "TestOrder": 3, "Rotation": "CCW"},
                            {"Number": 4, "TestOrder": 4, "Rotation": "CW"},
                        ],
                    }
                ]
            }
            mock_loader.data = mock_loader.load_json_data.return_value
            mock_json_class.return_value = mock_loader

            # Act: Initialize model
            model = MotorTestDataModel(mock_flight_controller, mock_filesystem)

            # Assert: JSON loader was configured and called correctly
            mock_json_class.assert_called_once()
            mock_loader.load_json_data.assert_called_once()
            assert model._motor_data == mock_loader.load_json_data.return_value

    def test_model_raises_error_with_empty_layouts(self, mock_flight_controller, mock_filesystem) -> None:
        """
        Model raises RuntimeError when no matching frame layout is found.

        GIVEN: JSON data loads successfully but contains no matching frame layouts
        WHEN: User initializes the motor test data model
        THEN: Model should raise RuntimeError about missing frame configuration
        """
        # Arrange: Mock JSON loading with empty layouts
        mock_flight_controller.get_frame_info.return_value = (1, 1)  # QUAD_X frame

        with patch("ardupilot_methodic_configurator.data_model_motor_test.FilesystemJSONWithSchema") as mock_json_class:
            mock_loader = MagicMock()
            mock_loader.load_json_data.return_value = {"layouts": []}
            mock_loader.data = mock_loader.load_json_data.return_value
            mock_json_class.return_value = mock_loader

            # Act & Assert: Initialize model should raise RuntimeError
            with pytest.raises(RuntimeError, match="No motor configuration found for frame class 1 and type 1"):
                MotorTestDataModel(mock_flight_controller, mock_filesystem)

    def test_model_handles_json_loading_failure_gracefully(self, mock_flight_controller, mock_filesystem) -> None:
        """
        Model raises RuntimeError when JSON loading fails.

        GIVEN: JSON loading fails due to file or validation errors
        WHEN: User initializes the motor test data model
        THEN: Model should raise RuntimeError since no frame configuration can be found
        """
        # Arrange: Mock JSON loading failure
        mock_flight_controller.get_frame_info.return_value = (1, 1)  # QUAD_X frame

        with patch("ardupilot_methodic_configurator.data_model_motor_test.FilesystemJSONWithSchema") as mock_json_class:
            mock_loader = MagicMock()
            mock_loader.load_json_data.side_effect = Exception("JSON loading failed")
            mock_loader.data = None  # When loading fails, data is None
            mock_json_class.return_value = mock_loader

            # Act & Assert: Initialize model should raise RuntimeError
            with pytest.raises(RuntimeError, match="No motor configuration found for frame class 1 and type 1"):
                MotorTestDataModel(mock_flight_controller, mock_filesystem)

    def test_model_handles_empty_json_response_appropriately(self, mock_flight_controller, mock_filesystem) -> None:
        """
        Model raises RuntimeError when JSON loading returns empty data.

        GIVEN: JSON loading returns empty data structure
        WHEN: User initializes the motor test data model
        THEN: Model should raise RuntimeError since no frame configuration can be found
        """
        # Arrange: Mock empty JSON response
        mock_flight_controller.get_frame_info.return_value = (1, 1)  # QUAD_X frame

        with patch("ardupilot_methodic_configurator.data_model_motor_test.FilesystemJSONWithSchema") as mock_json_class:
            mock_loader = MagicMock()
            mock_loader.load_json_data.return_value = {}
            mock_loader.data = {}  # Empty data
            mock_json_class.return_value = mock_loader

            # Act & Assert: Initialize model should raise RuntimeError
            with pytest.raises(RuntimeError, match="No motor configuration found for frame class 1 and type 1"):
                MotorTestDataModel(mock_flight_controller, mock_filesystem)

    def test_json_loader_configured_with_correct_schema_and_filename(self, mock_flight_controller, mock_filesystem) -> None:
        """
        JSON loader is configured with correct schema file and data filename.

        GIVEN: Motor test model initialization
        WHEN: JSON loader is instantiated
        THEN: Should be configured with AP_Motors_test.json and schema files
        """
        # Arrange: Mock JSON loader to capture initialization parameters
        with patch("ardupilot_methodic_configurator.data_model_motor_test.FilesystemJSONWithSchema") as mock_json_class:
            mock_loader = MagicMock()
            # Provide realistic mock data to allow initialization to succeed
            mock_data = {
                "layouts": [
                    {
                        "Class": 1,
                        "ClassName": "QUAD",
                        "Type": 1,
                        "TypeName": "X",
                        "motors": [
                            {"Number": 1, "TestOrder": 1, "Rotation": "CCW", "Roll": -0.5, "Pitch": 0.5},
                            {"Number": 2, "TestOrder": 2, "Rotation": "CW", "Roll": 0.5, "Pitch": 0.5},
                            {"Number": 3, "TestOrder": 3, "Rotation": "CW", "Roll": -0.5, "Pitch": -0.5},
                            {"Number": 4, "TestOrder": 4, "Rotation": "CCW", "Roll": 0.5, "Pitch": -0.5},
                        ],
                    }
                ]
            }
            mock_loader.load_json_data.return_value = mock_data
            mock_loader.data = mock_data
            mock_json_class.return_value = mock_loader

            # Mock frame parameters to match our test data (fc_parameters is dict[str, float])
            mock_flight_controller.fc_parameters = {"FRAME_CLASS": 1.0, "FRAME_TYPE": 1.0}

            # Act: Initialize model
            MotorTestDataModel(mock_flight_controller, mock_filesystem)

            # Assert: JSON loader configured with correct files
            mock_json_class.assert_called_once_with(
                json_filename="AP_Motors_test.json", schema_filename="AP_Motors_test_schema.json"
            )


# ==================== SETTINGS TESTS ====================


class TestMotorTestDataModelSettingsManagement:
    """Test user settings management for motor test parameters."""

    def test_user_can_get_test_duration_from_settings(self, motor_test_model) -> None:
        """
        User can retrieve the current motor test duration setting.

        GIVEN: A motor test model with stored settings
        WHEN: The user requests the current test duration
        THEN: The stored duration value should be returned
        """
        # Arrange: Mock settings to return a specific duration
        with patch.object(ProgramSettings, "get_setting", return_value="2.5") as mock_get:
            # Act: Get test duration
            duration = motor_test_model.get_test_duration()

            # Assert: Correct duration returned
            assert duration == 2.5
            mock_get.assert_called_once_with("motor_test/duration")

    def test_user_can_get_test_throttle_percentage_from_settings(self, motor_test_model) -> None:
        """
        User can retrieve the current motor test throttle percentage setting.

        GIVEN: A motor test model with stored settings
        WHEN: The user requests the current throttle percentage
        THEN: The stored throttle value should be returned
        """
        # Arrange: Mock settings to return a specific throttle percentage
        with patch.object(ProgramSettings, "get_setting", return_value="15") as mock_get:
            # Act: Get throttle percentage
            throttle = motor_test_model.get_test_throttle_pct()

            # Assert: Correct throttle returned
            assert throttle == 15
            mock_get.assert_called_once_with("motor_test/throttle_pct")

    def test_set_test_duration_handles_exception_gracefully(self, motor_test_model) -> None:
        """
        Setting test duration handles exceptions gracefully when save fails.

        GIVEN: A motor test model with settings that can fail to save
        WHEN: An exception occurs during settings save
        THEN: The method should return False and log the error
        """
        # Arrange: Mock settings to raise exception
        with (
            patch.object(ProgramSettings, "set_setting", side_effect=Exception("Settings save failed")),
            patch("ardupilot_methodic_configurator.data_model_motor_test.logging_error") as mock_log,
        ):
            # Act: Try to set duration
            result = motor_test_model.set_test_duration(2.0)

            # Assert: Failure handled gracefully
            assert result is False
            mock_log.assert_called_once()
            error_call = mock_log.call_args[0]
            assert "Failed to save duration setting" in error_call[0]

    def test_set_test_throttle_handles_exception_gracefully(self, motor_test_model) -> None:
        """
        Setting test throttle handles exceptions gracefully when save fails.

        GIVEN: A motor test model with settings that can fail to save
        WHEN: An exception occurs during settings save
        THEN: The method should return False and log the error
        """
        # Arrange: Mock settings to raise exception
        with (
            patch.object(ProgramSettings, "set_setting", side_effect=Exception("Settings save failed")),
            patch("ardupilot_methodic_configurator.data_model_motor_test.logging_error") as mock_log,
        ):
            # Act: Try to set throttle
            result = motor_test_model.set_test_throttle_pct(10)

            # Assert: Failure handled gracefully
            assert result is False
            mock_log.assert_called_once()
            error_call = mock_log.call_args[0]
            assert "Failed to save throttle percentage setting" in error_call[0]


class TestMotorTestDataModelSafetyChecksAdvanced:
    """Test advanced safety validation scenarios."""

    def test_motor_testing_unsafe_when_battery_status_unavailable(self, motor_test_model) -> None:
        """
        Motor testing is unsafe when battery status cannot be read.

        GIVEN: A motor test model with battery monitoring enabled
        WHEN: Battery status returns None (unreadable)
        THEN: Motor testing should be considered unsafe
        """
        # Arrange: Mock flight controller as connected but battery status unavailable
        motor_test_model.flight_controller.master = MagicMock()
        motor_test_model.flight_controller.fc_parameters = {
            "BATT_MONITOR": 4,  # Battery monitoring enabled
        }

        # Mock get_battery_status to return None
        with patch.object(motor_test_model, "get_battery_status", return_value=None):
            # Act: Check safety
            is_safe, message = motor_test_model.is_motor_test_safe()

            # Assert: Testing is unsafe due to unreadable battery
            assert is_safe is False
            assert "Could not read battery status" in message


class TestMotorTestDataModelFrameOptionsAdvanced:
    """Test advanced frame options parsing with edge cases."""

    def test_frame_options_handles_invalid_frame_class_values(self, motor_test_model_with_empty_json_data) -> None:
        """
        Frame options parsing handles invalid frame class values gracefully.

        GIVEN: A motor test model with malformed frame class documentation
        WHEN: Frame class values contain invalid data types
        THEN: Invalid entries should be skipped without errors
        """
        # Arrange: Mock filesystem with invalid frame class values
        motor_test_model_with_empty_json_data.filesystem = MagicMock()
        motor_test_model_with_empty_json_data.filesystem.doc_dict = {
            "FRAME_CLASS": {
                "values": {
                    "1": "Quad",  # Valid
                    "invalid": "Bad",  # Invalid key
                    "2.5": "Float",  # Invalid key type
                    None: "None",  # Invalid key type
                    "3": "Hexa",  # Valid
                }
            },
            "FRAME_TYPE": {
                "values": {
                    "0": "Quad: Plus",  # Valid frame type
                    "1": "Quad: X",  # Valid frame type
                }
            },
        }

        # Ensure motor data is completely empty to trigger fallback
        motor_test_model_with_empty_json_data._motor_data_loader.data = None

        # Act: Get frame options
        frame_options = motor_test_model_with_empty_json_data.get_frame_options()

        # Assert: Only valid entries are included
        assert "QUAD" in frame_options  # Valid entry from frame type parsing
        assert 0 in frame_options["QUAD"]  # Frame type entry by key
        assert frame_options["QUAD"][0] == "Plus"  # Frame type value
        assert "invalid" not in str(frame_options)  # Invalid entries excluded

    def test_frame_options_handles_invalid_frame_type_values(self, motor_test_model) -> None:
        """
        Frame options parsing handles invalid frame type values gracefully.

        GIVEN: A motor test model with malformed frame type documentation
        WHEN: Frame type values contain invalid data types
        THEN: Invalid entries should be skipped without errors
        """
        # Arrange: Mock filesystem with invalid frame type values
        motor_test_model.filesystem = MagicMock()
        motor_test_model.filesystem.doc_dict = {
            "FRAME_CLASS": {"values": {"1": "Quad"}},
            "FRAME_TYPE": {
                "values": {
                    "0": "Quad: Plus",  # Valid format
                    "invalid": "Bad",  # Invalid key
                    "1.5": "Float",  # Invalid key type
                    None: "None",  # Invalid key type
                    "1": "Quad: X",  # Valid format
                }
            },
        }

        # Act: Get frame options
        frame_options = motor_test_model.get_frame_options()

        # Assert: Only valid entries are included
        assert "QUAD" in frame_options
        assert 0 in frame_options["QUAD"]  # Valid entry "Plus"
        assert 1 in frame_options["QUAD"]  # Valid entry "X"
        # Invalid entries should be excluded without breaking the parsing


class TestMotorTestDataModelConnectionRefresh:
    """Test connection status refresh with error handling."""

    def test_refresh_connection_status_handles_frame_update_exception(self, motor_test_model) -> None:
        """
        Connection refresh handles frame configuration update exceptions gracefully.

        GIVEN: A motor test model with a connected flight controller
        WHEN: Frame configuration update raises a RuntimeError
        THEN: The refresh should return False without propagating the exception
        """
        # Arrange: Mock _update_frame_configuration to raise RuntimeError
        with patch.object(motor_test_model, "_update_frame_configuration", side_effect=RuntimeError("Update failed")):
            # Act: Try to refresh connection status
            result = motor_test_model.refresh_connection_status()

            # Assert: Exception handled gracefully
            assert result is False

    def test_refresh_connection_status_succeeds_with_successful_update(self, motor_test_model) -> None:
        """
        Connection refresh succeeds when frame configuration updates successfully.

        GIVEN: A motor test model with a connected flight controller
        WHEN: Frame configuration update succeeds
        THEN: The refresh should return True
        """
        # Arrange: Mock _update_frame_configuration to succeed
        with patch.object(motor_test_model, "_update_frame_configuration", return_value=None):
            # Act: Refresh connection status
            result = motor_test_model.refresh_connection_status()

            # Assert: Refresh succeeded
            assert result is True


class TestMotorTestDataModelSettingsPersistence:
    """Test settings persistence success paths for complete coverage."""

    def test_set_test_duration_succeeds_with_valid_value(self, motor_test_model) -> None:
        """
        Test duration setting saves successfully with valid values.

        GIVEN: A motor test model and valid duration value
        WHEN: User saves test duration within valid range (0.1-10.0)
        THEN: Should save setting and return True
        """
        # Arrange: Valid duration value
        duration = 2.5

        # Act: Save test duration
        with patch("ardupilot_methodic_configurator.data_model_motor_test.ProgramSettings.set_setting") as mock_set:
            result = motor_test_model.set_test_duration(duration)

            # Assert: Setting saved successfully
            assert result is True
            mock_set.assert_called_once_with("motor_test/duration", duration)

    def test_set_test_throttle_pct_succeeds_with_valid_value(self, motor_test_model) -> None:
        """
        Test throttle percentage setting saves successfully with valid values.

        GIVEN: A motor test model and valid throttle percentage
        WHEN: User saves throttle percentage within valid range (1-100)
        THEN: Should save setting and return True
        """
        # Arrange: Valid throttle percentage
        throttle = 50

        # Act: Save throttle percentage
        with patch("ardupilot_methodic_configurator.data_model_motor_test.ProgramSettings.set_setting") as mock_set:
            result = motor_test_model.set_test_throttle_pct(throttle)

            # Assert: Setting saved successfully
            assert result is True
            mock_set.assert_called_once_with("motor_test/throttle_pct", throttle)


class TestSettingsExceptionHandling:
    """Test exception handling in settings persistence methods."""

    def test_set_test_duration_handles_exceptions(self, motor_test_model) -> None:
        """
        Test that set_test_duration handles exceptions gracefully.

        GIVEN: A motor test model with mocked settings that raises exceptions
        WHEN: Attempting to save test duration
        THEN: Should return False and log error
        """
        # Arrange: Mock ProgramSettings to raise exception
        with patch("ardupilot_methodic_configurator.data_model_motor_test.ProgramSettings") as mock_settings:
            mock_settings.set_setting.side_effect = Exception("Settings error")

            # Act: Try to save test duration
            result = motor_test_model.set_test_duration(2.0)

            # Assert: Should return False
            assert result is False

    def test_set_test_throttle_pct_handles_exceptions(self, motor_test_model) -> None:
        """
        Test that set_test_throttle_pct handles exceptions gracefully.

        GIVEN: A motor test model with mocked settings that raises exceptions
        WHEN: Attempting to save test throttle
        THEN: Should return False and log error
        """
        # Arrange: Mock ProgramSettings to raise exception
        with patch("ardupilot_methodic_configurator.data_model_motor_test.ProgramSettings") as mock_settings:
            mock_settings.set_setting.side_effect = Exception("Settings error")

            # Act: Try to save test throttle
            result = motor_test_model.set_test_throttle_pct(50)

            # Assert: Should return False
            assert result is False

    def test_refresh_from_flight_controller_handles_runtime_error(self, motor_test_model) -> None:
        """
        Test that refresh_from_flight_controller handles RuntimeError gracefully.

        GIVEN: A motor test model where _update_frame_configuration raises RuntimeError
        WHEN: Refreshing from flight controller
        THEN: Should return False instead of propagating exception
        """
        # Arrange: Mock _update_frame_configuration to raise RuntimeError
        with patch.object(motor_test_model, "_update_frame_configuration", side_effect=RuntimeError("Connection error")):
            # Act: Refresh from flight controller
            result = motor_test_model.refresh_from_flight_controller()

            # Assert: Should return False
            assert result is False

    def test_refresh_from_flight_controller_succeeds_when_update_works(self, motor_test_model) -> None:
        """
        Test that refresh_from_flight_controller returns True when update succeeds.

        GIVEN: A motor test model where _update_frame_configuration works normally
        WHEN: Refreshing from flight controller
        THEN: Should return True
        """
        # Arrange: Mock _update_frame_configuration to succeed
        with patch.object(motor_test_model, "_update_frame_configuration", return_value=None):
            # Act: Refresh from flight controller
            result = motor_test_model.refresh_from_flight_controller()

            # Assert: Should return True
            assert result is True
