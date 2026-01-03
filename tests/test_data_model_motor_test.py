#!/usr/bin/env python3

"""
Tests for the data_model_motor_test.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_program_settings import ProgramSettings
from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.data_model_motor_test import (
    FlightControllerConnectionError,
    FrameConfigurationError,
    MotorStatusEvent,
    MotorTestDataModel,
    MotorTestExecutionError,
    MotorTestSafetyError,
    ParameterError,
    ValidationError,
)

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

    # Configure set_param to update fc_parameters and return success
    def set_param_side_effect(param_name: str, value: float) -> tuple[bool, str]:
        fc.fc_parameters[param_name] = value
        return (True, "")

    fc.set_param.side_effect = set_param_side_effect

    # Configure fetch_param to return values from fc_parameters
    def fetch_param_side_effect(param_name: str) -> Optional[float]:
        value = fc.fc_parameters.get(param_name)
        if isinstance(value, (int, float)):
            return float(value)
        return None

    fc.fetch_param.side_effect = fetch_param_side_effect

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
            },
            "min": 1,
            "max": 12,
            "RebootRequired": True,
        },
        "FRAME_TYPE": {
            "values": {
                "0": "QUAD: PLUS",
                "1": "QUAD: X",
                "2": "HEXA: PLUS",
                "3": "HEXA: X",
                "10": "OCTA: PLUS",
                "11": "OCTA: X",
            },
            "min": 0,
            "max": 14,
            "RebootRequired": False,
        },
        "MOT_SPIN_ARM": {
            "min": 0.05,
            "max": 0.40,
            "RebootRequired": True,
        },
        "MOT_SPIN_MIN": {
            "min": 0.07,
            "max": 0.50,
            "RebootRequired": False,
        },
    }

    return filesystem


@pytest.fixture(autouse=True)
def program_settings_store(monkeypatch) -> dict[str, Any]:
    """Provide in-memory ProgramSettings storage for deterministic tests."""
    store: dict[str, Any] = {"motor_test": {"duration": 3.0, "throttle_pct": 12}}

    def _get_setting(setting: str) -> Optional[float]:
        parts = setting.split("/")
        current: Any = store
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        if isinstance(current, (int, float)):
            return float(current)
        return None

    def _set_setting(setting: str, value: float) -> None:
        parts = setting.split("/")
        current: Any = store
        for part in parts[:-1]:
            next_part = current.setdefault(part, {})
            if not isinstance(next_part, dict):
                next_part = {}
                current[part] = next_part
            current = next_part
        current[parts[-1]] = float(value)

    monkeypatch.setattr(
        "ardupilot_methodic_configurator.data_model_motor_test.ProgramSettings.get_setting",
        _get_setting,
    )
    monkeypatch.setattr(
        "ardupilot_methodic_configurator.data_model_motor_test.ProgramSettings.set_setting",
        _set_setting,
    )
    return store


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
        assert model.motor_count == 4
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
        labels = motor_test_model.motor_labels

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
        numbers = motor_test_model.motor_numbers

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
            motor_test_model.update_frame_configuration(2, 1)  # Hexa X

            # Assert: Update successful
            assert motor_test_model.frame_class == 2
            assert motor_test_model.frame_type == 1
            assert motor_test_model.motor_count == 6  # HEXA X has 6 motors

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
            motor_test_model.update_frame_configuration(frame_class=2, frame_type=1)

            # Assert: Configuration updated successfully
            assert motor_test_model.frame_class == 2
            assert motor_test_model.frame_type == 1
            assert motor_test_model.motor_count == 6  # HEXA X has 6 motors

    def test_frame_configuration_update_handles_missing_layouts(self, motor_test_model) -> None:
        """Missing layout data leaves motor counts at zero without crashing."""
        motor_test_model._motor_data_loader.data = {"layouts": []}  # pylint: disable=protected-access
        motor_test_model._frame_class = 3  # pylint: disable=protected-access
        motor_test_model._frame_type = 3  # pylint: disable=protected-access

        with patch.object(motor_test_model, "set_parameter", return_value=(True, "")):
            motor_test_model.update_frame_configuration(1, 1)

        assert motor_test_model.motor_count == 0

    def test_frame_configuration_update_skips_recalc_when_data_missing(self, motor_test_model) -> None:
        """When the loader lacks data entirely the recalc block is skipped."""
        motor_test_model._motor_data_loader.data = None  # pylint: disable=protected-access

        with patch.object(motor_test_model, "set_parameter", return_value=(True, "")):
            motor_test_model.update_frame_configuration(1, 1)

        assert motor_test_model.motor_count == 0

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
        THEN: Should raise FlightControllerConnectionError with clear error message
        """
        # Arrange: Create model with disconnected FC (will fail initialization)
        # We'll test this by mocking the model's flight controller directly
        with patch("ardupilot_methodic_configurator.data_model_motor_test.MotorTestDataModel._update_frame_configuration"):
            model = MotorTestDataModel(flight_controller=disconnected_flight_controller, filesystem=mock_filesystem)
            model.flight_controller = disconnected_flight_controller

            # Act & Assert: Attempt frame configuration update should raise exception
            with pytest.raises(FlightControllerConnectionError, match="Flight controller connection required"):
                model.update_frame_configuration(frame_class=2, frame_type=1)


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
        THEN: Should not raise any exceptions (test is safe)
        """
        # Arrange: Good conditions configured in fixture

        # Act: Check motor testing safety - should not raise exceptions
        motor_test_model.is_motor_test_safe()

        # Assert: If we reach here, the test is safe (no exceptions raised)

    def test_motor_testing_unsafe_with_disconnected_controller(self, motor_test_model) -> None:
        """
        Motor testing is unsafe when flight controller is disconnected.

        GIVEN: Motor test model with disconnected flight controller
        WHEN: User checks if motor testing is safe
        THEN: Should raise FlightControllerConnectionError with appropriate error message
        """
        # Arrange: Disconnect flight controller
        motor_test_model.flight_controller.master = None

        # Act & Assert: Check motor testing safety should raise exception
        with pytest.raises(FlightControllerConnectionError, match="not connected"):
            motor_test_model.is_motor_test_safe()

    def test_motor_testing_unsafe_with_no_battery_monitoring(self, motor_test_model) -> None:
        """
        Motor testing is unsafe when flight controller is disconnected.

        GIVEN: A disconnected flight controller
        WHEN: User checks if motor testing is safe
        THEN: Should raise FlightControllerConnectionError with connection error message
        """
        # Arrange: Disconnect flight controller
        motor_test_model.flight_controller.master = None

        # Act & Assert: Check motor test safety should raise exception
        with pytest.raises(FlightControllerConnectionError, match="Flight controller not connected"):
            motor_test_model.is_motor_test_safe()

    def test_motor_testing_safe_with_battery_monitoring_disabled(self, motor_test_model) -> None:
        """
        Motor testing is safe when battery monitoring is disabled.

        GIVEN: A flight controller with battery monitoring disabled
        WHEN: User checks if motor testing is safe
        THEN: Should not raise exceptions but log warning about disabled monitoring
        """
        # Arrange: Disable battery monitoring
        motor_test_model.flight_controller.is_battery_monitoring_enabled.return_value = False

        # Act: Check motor test safety - should not raise exceptions
        motor_test_model.is_motor_test_safe()

        # Assert: If we reach here, test is safe despite disabled monitoring

    def test_motor_testing_unsafe_with_low_voltage(self, motor_test_model) -> None:
        """
        Motor testing is unsafe when battery voltage is below minimum threshold.

        GIVEN: A battery with voltage below the minimum threshold
        WHEN: User checks if motor testing is safe
        THEN: Should raise MotorTestSafetyError with low voltage warning
        """
        # Arrange: Set voltage below minimum threshold
        motor_test_model.flight_controller.get_battery_status.return_value = ((10.5, 2.1), "")
        _min_voltage, _max_voltage = motor_test_model.get_voltage_thresholds()

        # Act & Assert: Check motor test safety should raise exception
        with pytest.raises(MotorTestSafetyError, match=r"Battery voltage 10.5V is outside safe range"):
            motor_test_model.is_motor_test_safe()

    def test_motor_testing_unsafe_with_high_voltage(self, motor_test_model) -> None:
        """
        Motor testing is unsafe when battery voltage is above maximum threshold.

        GIVEN: A battery with voltage above the maximum threshold
        WHEN: User checks if motor testing is safe
        THEN: Should raise MotorTestSafetyError with high voltage warning
        """
        # Arrange: Set voltage above maximum threshold
        motor_test_model.flight_controller.get_battery_status.return_value = ((17.0, 2.1), "")
        _min_voltage, _max_voltage = motor_test_model.get_voltage_thresholds()

        # Act & Assert: Check motor test safety should raise exception
        with pytest.raises(MotorTestSafetyError, match=r"Battery voltage 17.0V is outside safe range"):
            motor_test_model.is_motor_test_safe()


class TestMotorTestDataModelParameterManagement:
    """Test parameter setting and validation."""

    def test_user_can_set_motor_parameter_successfully(self, motor_test_model) -> None:
        """
        User can successfully set motor parameters with verification.

        GIVEN: A connected flight controller and valid parameter
        WHEN: User sets a motor parameter
        THEN: Parameter should be set successfully without raising exceptions
        """
        # Arrange: Configure parameter reading
        motor_test_model.flight_controller.fc_parameters["MOT_SPIN_ARM"] = 0.12

        # Act: Set parameter - should not raise exceptions
        motor_test_model.set_parameter("MOT_SPIN_ARM", 0.12)

        # Assert: If we reach here, parameter was set successfully
        motor_test_model.flight_controller.set_param.assert_called_once_with("MOT_SPIN_ARM", 0.12)

    def test_parameter_setting_fails_with_disconnected_controller(self, motor_test_model) -> None:
        """
        Parameter setting fails when flight controller is disconnected.

        GIVEN: A disconnected flight controller
        WHEN: User attempts to set a parameter
        THEN: Should raise FlightControllerConnectionError with connection error
        """
        # Arrange: Disconnect flight controller
        motor_test_model.flight_controller.master = None

        # Act & Assert: Attempt to set parameter should raise exception
        with pytest.raises(FlightControllerConnectionError, match="No flight controller connection available"):
            motor_test_model.set_parameter("MOT_SPIN_ARM", 0.12)

    def test_parameter_validation_rejects_out_of_bounds_values(self, motor_test_model) -> None:
        """
        Parameter validation rejects values outside acceptable range.

        GIVEN: A motor parameter with defined bounds
        WHEN: User attempts to set value outside bounds
        THEN: Should raise ValidationError with validation error
        """
        # Arrange: Parameter bounds defined in code (0.0 - 1.0)

        # Act & Assert: Attempt to set out-of-bounds value should raise exception
        with pytest.raises(ValidationError, match=r"outside valid range \(0.0 - 1.0\)"):
            motor_test_model.set_parameter("MOT_SPIN_ARM", 1.5)

    def test_parameter_verification_detects_setting_failure(self, motor_test_model) -> None:
        """
        Parameter verification detects when setting appears successful but value differs.

        GIVEN: A parameter that appears to set but reads back differently
        WHEN: User sets the parameter
        THEN: Should raise ParameterError with verification error
        """
        # Arrange: Override fetch_param to return different value for verification failure
        motor_test_model.flight_controller.fetch_param.side_effect = None  # Clear side_effect
        motor_test_model.flight_controller.fetch_param.return_value = 0.10  # Different from set value

        # Act & Assert: Set parameter with different result should raise exception
        with pytest.raises(ParameterError, match="verification failed"):
            motor_test_model.set_parameter("MOT_SPIN_ARM", 0.12)

    def test_parameter_setting_triggers_reset_when_required(self, motor_test_model) -> None:
        """Parameters flagged as reboot-required trigger a reconnect once applied."""
        reset_callback = MagicMock(name="reset_cb")
        reconnect_callback = MagicMock(name="reconnect_cb")
        motor_test_model.flight_controller.reset_and_reconnect = MagicMock()

        motor_test_model.set_parameter(
            "MOT_SPIN_ARM",
            0.2,
            reset_progress_callback=reset_callback,
            connection_progress_callback=reconnect_callback,
            extra_sleep_time=7,
        )

        motor_test_model.flight_controller.reset_and_reconnect.assert_called_once_with(
            reset_callback,
            reconnect_callback,
            7,
        )

    def test_parameter_setting_raises_error_when_verification_fails(self, motor_test_model) -> None:
        """A mismatched readback raises ParameterError with helpful context."""
        motor_test_model.flight_controller.fetch_param = MagicMock(return_value=0.01)

        with pytest.raises(ParameterError, match="verification failed"):
            motor_test_model.set_parameter("MOT_SPIN_MIN", 0.3)

    def test_parameter_setting_skips_doc_metadata_when_missing(self, motor_test_model) -> None:
        """Parameters without documentation skip metadata validation gracefully."""
        motor_test_model.filesystem.doc_dict.pop("MOT_SPIN_ARM", None)
        motor_test_model.flight_controller.fc_parameters["CUSTOM_PARAM"] = 0.05

        motor_test_model.set_parameter("CUSTOM_PARAM", 0.07)

        motor_test_model.flight_controller.set_param.assert_any_call("CUSTOM_PARAM", 0.07)

    def test_parameter_setting_raises_error_when_controller_rejects_change(self, motor_test_model) -> None:
        """Controller rejection surfaces a ParameterError with the FC message."""
        motor_test_model.flight_controller.set_param.side_effect = None
        motor_test_model.flight_controller.set_param.return_value = (False, "DENIED")

        with pytest.raises(ParameterError, match="Failed to set parameter"):
            motor_test_model.set_parameter("MOT_SPIN_ARM", 0.2)

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
        THEN: Motor test should be executed successfully without raising exceptions
        """
        # Arrange: Safe conditions configured in fixture

        # Act: Test motor 1 (test_sequence_nr=0, motor_output_nr=1) at 10% throttle for 2 seconds
        motor_test_model.test_motor(0, 1, 10, 2)

        # Assert: Motor test successful (verified that flight controller was called with correct parameters)
        motor_test_model.flight_controller.test_motor.assert_called_once_with(0, "A", 1, 10, 2)

    def test_motor_test_fails_with_invalid_motor_number(self, motor_test_model) -> None:
        """
        Motor test fails when invalid motor number is specified.

        GIVEN: Motor test model with 4-motor configuration
        WHEN: User attempts to test motor 5 (out of range)
        THEN: Should raise ValidationError with descriptive error message
        """
        # Arrange: 4-motor configuration in fixture

        # Act & Assert: Attempt to test invalid test sequence number (4 is out of range for 4-motor config)
        with pytest.raises(ValidationError, match="Invalid test sequence number"):
            motor_test_model.test_motor(4, 5, 10, 2)

    def test_motor_test_fails_with_invalid_motor_number2(self, motor_test_model) -> None:
        """
        Motor test fails when user specifies invalid motor number.

        GIVEN: A 4-motor vehicle configuration
        WHEN: User attempts to test motor number outside valid range
        THEN: Should raise ValidationError with motor number validation message
        """
        # Arrange: 4-motor configuration in fixture

        # Act & Assert: Test invalid motor output number should raise ValidationError
        with pytest.raises(ValidationError, match=r"Invalid motor output number 5"):
            motor_test_model.test_motor(0, 5, 10, 2)  # test_sequence_nr=0, motor_output_nr=5 (invalid)

    def test_motor_test_fails_with_invalid_throttle_percentage(self, motor_test_model) -> None:
        """
        Motor test fails when user specifies invalid throttle percentage.

        GIVEN: Safe conditions for motor testing
        WHEN: User attempts test with throttle outside valid range
        THEN: Should raise ValidationError with throttle validation message
        """
        # Arrange: Safe conditions configured in fixture

        # Act & Assert: Test with invalid throttle should raise ValidationError
        with pytest.raises(ValidationError, match=r"Invalid throttle percentage 150 \(valid range: 1-100\)"):
            motor_test_model.test_motor(0, 1, 150, 2)

    def test_motor_test_fails_under_unsafe_conditions(self, motor_test_model) -> None:
        """
        Motor test fails when safety conditions are not met.

        GIVEN: Unsafe battery voltage conditions
        WHEN: User attempts motor test
        THEN: Should raise MotorTestSafetyError with safety message
        """
        # Arrange: Set unsafe battery voltage
        motor_test_model.flight_controller.get_battery_status.return_value = ((10.0, 2.1), "")

        # Act & Assert: Attempt motor test should raise MotorTestSafetyError
        with pytest.raises(MotorTestSafetyError, match=r"Battery voltage 10\.0V is outside safe range"):
            motor_test_model.test_motor(0, 1, 10, 2)

    def test_user_can_test_all_motors_simultaneously(self, motor_test_model) -> None:
        """
        User can successfully test all motors simultaneously.

        GIVEN: Safe conditions for motor testing
        WHEN: User tests all motors
        THEN: All motors test should execute successfully without exception
        """
        # Arrange: Safe conditions configured in fixture

        # Act: Test all motors (should not raise exception)
        motor_test_model.test_all_motors(throttle_percent=10, timeout_seconds=2)

        # Assert: Verify method was called correctly
        motor_test_model.flight_controller.test_all_motors.assert_called_once_with(4, 10, 2)

    def test_user_can_test_motors_in_sequence(self, motor_test_model) -> None:
        """
        User can successfully test motors in sequence.

        GIVEN: Safe conditions for motor testing
        WHEN: User tests motors in sequence
        THEN: Sequential test should execute successfully without exception
        """
        # Arrange: Safe conditions configured in fixture

        # Act: Test motors in sequence (should not raise exception)
        motor_test_model.test_motors_in_sequence(throttle_percent=10, timeout_seconds=2)

        # Assert: Verify method was called correctly
        motor_test_model.flight_controller.test_motors_in_sequence.assert_called_once_with(1, 4, 10, 2)

    def test_user_can_stop_all_motors_emergency(self, motor_test_model) -> None:
        """
        User can emergency stop all motors at any time.

        GIVEN: Motors potentially running
        WHEN: User triggers emergency stop
        THEN: All motors should stop immediately without exception
        """
        # Arrange: No special setup needed

        # Act: Emergency stop (should not raise exception)
        motor_test_model.stop_all_motors()

        # Assert: Verify method was called correctly
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
        THEN: Should raise ParameterError with appropriate message
        """
        # Arrange: Configure communication error
        motor_test_model.flight_controller.set_param.side_effect = Exception("Communication timeout")

        # Act & Assert: Attempt parameter setting should raise ParameterError
        with pytest.raises(ParameterError, match=r"Communication timeout"):
            motor_test_model.set_parameter("MOT_SPIN_ARM", 0.12)

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
        # Arrange: Mock an exception during frame configuration
        # Act & Assert: Exception should be caught and re-raised
        with (
            patch.object(MotorTestDataModel, "_update_frame_configuration", side_effect=Exception("Test exception")),
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
        with patch("ardupilot_methodic_configurator.data_model_battery_monitor.logging_warning") as mock_warning:
            result = motor_test_model.get_battery_status()

            # Assert
            assert result is None
            mock_warning.assert_called_once_with(_("Flight controller not connected, cannot get battery status."))

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
        THEN: Should raise MotorTestSafetyError with safety reason
        """
        # Arrange: Make conditions unsafe by mocking is_motor_test_safe to raise exception
        with (
            patch.object(motor_test_model, "is_motor_test_safe", side_effect=MotorTestSafetyError("Unsafe voltage")),
            pytest.raises(MotorTestSafetyError, match=r"Unsafe voltage"),
        ):
            # Act: Attempt motor test should raise MotorTestSafetyError
            motor_test_model.test_all_motors(50, 3)

    def test_sequential_motor_test_with_unsafe_conditions(self, motor_test_model) -> None:
        """
        Sequential motor test fails when safety conditions are not met.

        GIVEN: A motor test model with unsafe conditions
        WHEN: Attempting to test motors in sequence
        THEN: Should raise MotorTestSafetyError with safety reason
        """
        # Arrange: Make conditions unsafe by mocking is_motor_test_safe to raise exception
        with (
            patch.object(motor_test_model, "is_motor_test_safe", side_effect=MotorTestSafetyError("Battery too low")),
            pytest.raises(MotorTestSafetyError, match=r"Battery too low"),
        ):
            # Act: Attempt sequential motor test should raise MotorTestSafetyError
            motor_test_model.test_motors_in_sequence(throttle_percent=30, timeout_seconds=2)

    def test_set_test_duration_exception_handling(self, motor_test_model) -> None:
        """
        Set test duration handles exceptions gracefully.

        GIVEN: A motor test model
        WHEN: An exception occurs while setting test duration
        THEN: Should return False and log error
        """
        # Arrange: Mock exception in ProgramSettings.set_setting
        # Act & Assert: Attempt to set duration should raise exception
        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.set_setting",
                side_effect=Exception("Save error"),
            ),
            pytest.raises(Exception, match="Save error"),
        ):
            motor_test_model.set_test_duration_s(5)

    def test_set_test_throttle_exception_handling(self, motor_test_model) -> None:
        """
        Set test throttle handles exceptions gracefully.

        GIVEN: A motor test model
        WHEN: An exception occurs while setting test throttle
        THEN: Should return False and log error
        """
        # Arrange: Mock exception in ProgramSettings.set_setting
        # Act & Assert: Attempt to set throttle should raise exception
        with (
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.set_setting",
                side_effect=Exception("Save error"),
            ),
            pytest.raises(Exception, match="Save error"),
        ):
            motor_test_model.set_test_throttle_pct(75)

    def test_update_frame_configuration_class_parameter_failure(self, motor_test_model) -> None:
        """
        Frame configuration update fails when FRAME_CLASS parameter setting fails.

        GIVEN: A motor test model
        WHEN: Setting FRAME_CLASS parameter fails
        THEN: Should raise ParameterError with appropriate error message
        """
        # Arrange: Mock parameter setting to fail for FRAME_CLASS
        with patch.object(motor_test_model, "set_parameter") as mock_set_param:
            mock_set_param.side_effect = [
                ParameterError("Failed to set FRAME_CLASS"),  # First call fails
                None,  # Second call would succeed but shouldn't be reached
            ]

            # Act & Assert: Attempt frame configuration update should raise ParameterError
            with pytest.raises(ParameterError, match=r"Failed to set FRAME_CLASS"):
                motor_test_model.update_frame_configuration(2, 0)

    def test_update_frame_configuration_type_parameter_failure(self, motor_test_model) -> None:
        """
        Frame configuration update fails when FRAME_TYPE parameter setting fails.

        GIVEN: A motor test model
        WHEN: Setting FRAME_TYPE parameter fails
        THEN: Should raise ParameterError with appropriate error message
        """
        # Arrange: Mock parameter setting to fail for FRAME_TYPE
        with patch.object(motor_test_model, "set_parameter") as mock_set_param:
            mock_set_param.side_effect = [
                None,  # FRAME_CLASS succeeds (void)
                ParameterError("Failed to set FRAME_TYPE"),  # FRAME_TYPE fails
            ]

            # Act & Assert: Attempt frame configuration update should raise ParameterError
            with pytest.raises(ParameterError, match=r"Failed to set FRAME_TYPE"):
                motor_test_model.update_frame_configuration(2, 0)

    def test_update_frame_configuration_exception_during_update(self, motor_test_model) -> None:
        """
        Frame configuration update handles exceptions during the update process.

        GIVEN: A motor test model
        WHEN: An exception occurs during the update process
        THEN: Should raise FrameConfigurationError with error message
        """
        # Arrange: Mock an exception during the update process
        with patch.object(motor_test_model, "set_parameter") as mock_set_param:
            mock_set_param.side_effect = Exception("Internal error during parameter setting")

            # Act & Assert: Attempt frame configuration update should raise FrameConfigurationError
            with pytest.raises(
                FrameConfigurationError, match=r"Failed to update frame configuration: Internal error during parameter setting"
            ):
                motor_test_model.update_frame_configuration(2, 0)

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
        directions = model.motor_directions

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
        model._configure_frame_layout(frame_class=1, frame_type=0)

        # Act: Get motor directions
        directions = model.motor_directions

        # Assert: Correct PLUS frame directions in test order
        # TestOrder 1: Motor 3 (CW), TestOrder 2: Motor 1 (CCW), TestOrder 3: Motor 4 (CW), TestOrder 4: Motor 2 (CCW)
        expected_directions = ["CW", "CCW", "CW", "CCW"]  # Ordered by TestOrder from mock JSON for QUAD PLUS
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
        model._configure_frame_layout(frame_class=2, frame_type=1)

        # Act: Get motor directions
        directions = model.motor_directions

        # Assert: Correct HEXA frame directions
        # From JSON: TestOrder 1-6 → Motors 1-6 → CW,CCW,CW,CCW,CW,CCW
        expected_directions = ["CW", "CCW", "CW", "CCW", "CW", "CCW"]  # From mock JSON for HEXA X
        assert directions == expected_directions
        assert len(directions) == 6

    def test_user_gets_empty_directions_when_frame_not_found_in_json(self, motor_test_model_with_json_data) -> None:
        """
        User gets empty motor directions when frame configuration not found in JSON.

        GIVEN: A motor test model with JSON data
        WHEN: User requests directions for unsupported frame configuration
        THEN: Should return empty motor directions list
        """
        # Arrange: Configure unsupported frame (class=99, type=99)
        model = motor_test_model_with_json_data
        model._frame_class = 99
        model._frame_type = 99
        model._motor_count = 0
        model._motor_directions = []  # No frame layout found

        # Act: Get motor directions
        directions = model.motor_directions

        # Assert: Should return empty list
        assert directions == []

    def test_user_gets_empty_directions_when_json_data_empty(self, motor_test_model_with_empty_json_data) -> None:
        """
        User gets empty motor directions when JSON data is empty or invalid.

        GIVEN: A motor test model with empty or failed JSON data loading
        WHEN: User requests motor directions
        THEN: Should return empty motor directions list
        """
        # Arrange: Model with empty JSON data from fixture
        model = motor_test_model_with_empty_json_data
        model._motor_directions = []  # No frame layout available

        # Act: Get motor directions
        directions = model.motor_directions

        # Assert: Should return empty list
        assert directions == []

    def test_user_gets_empty_directions_when_json_data_corrupted(self, motor_test_model_with_corrupted_json_data) -> None:
        """
        User gets empty motor directions when JSON data structure is invalid.

        GIVEN: A motor test model with corrupted JSON data structure
        WHEN: User requests motor directions
        THEN: Should return empty motor directions list
        """
        # Arrange: Model with corrupted JSON data from fixture
        model = motor_test_model_with_corrupted_json_data

        # Act: Get motor directions
        directions = model.motor_directions

        # Assert: Should return empty list
        assert directions == []

    def test_motor_directions_unchanged_when_count_manually_increased(self, motor_test_model_with_json_data) -> None:
        """
        Motor directions remain unchanged when motor count is manually increased.

        GIVEN: A motor test model where JSON has fewer motors than expected
        WHEN: User manually increases motor count after configuration
        THEN: Should return original directions (implementation doesn't auto-extend)
        """
        # Arrange: Configure frame with valid class/type then simulate motor count mismatch
        model = motor_test_model_with_json_data
        with patch.object(model, "set_parameter", return_value=(True, None)):
            model.update_frame_configuration(1, 1)  # Configure QUAD X frame (has 4 motors)

        # Manually increase motor count to simulate mismatch
        model._motor_count = 8  # Expect 8 motors but frame layout only has 4

        # Act: Get motor directions
        directions = model.motor_directions

        # Assert: Directions list has original length (no auto-extension)
        assert len(directions) == 4
        expected_directions = ["CCW", "CW", "CW", "CCW"]  # From mock JSON for QUAD X
        assert directions == expected_directions

    def test_motor_directions_unchanged_when_count_manually_decreased(self, motor_test_model_with_json_data) -> None:
        """
        Motor directions remain unchanged when motor count is manually decreased.

        GIVEN: A motor test model where JSON has more motors than expected
        WHEN: User manually decreases motor count after configuration
        THEN: Should return original directions (implementation doesn't auto-truncate)
        """
        # Arrange: Configure frame with valid class/type then simulate motor count mismatch
        model = motor_test_model_with_json_data

        # Configure HEXA frame directly without using update_frame_configuration
        model._configure_frame_layout(2, 1)  # Configure HEXA frame (has 6 motors)

        # Manually decrease motor count to simulate mismatch
        original_directions = model.motor_directions.copy()  # Save original directions
        model._motor_count = 4  # Expect only 4 motors but frame layout has 6

        # Act: Get motor directions
        directions = model.motor_directions

        # Assert: Directions remain original (implementation doesn't auto-truncate based on motor count)
        expected_directions = ["CW", "CCW", "CW", "CCW", "CW", "CCW"]  # From mock JSON for HEXA X
        assert directions == expected_directions
        assert directions == original_directions


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
        # Arrange: Set internal duration value
        motor_test_model._test_duration_s = 2.5

        # Act: Get test duration
        duration = motor_test_model.get_test_duration_s()

        # Assert: Correct duration returned
        assert duration == 2.5

    def test_user_can_get_test_throttle_percentage_from_settings(self, motor_test_model) -> None:
        """
        User can retrieve the current motor test throttle percentage setting.

        GIVEN: A motor test model with stored settings
        WHEN: The user requests the current throttle percentage
        THEN: The stored throttle value should be returned
        """
        # Arrange: Set internal throttle value
        motor_test_model._test_throttle_pct = 15

        # Act: Get throttle percentage
        throttle = motor_test_model.get_test_throttle_pct()

        # Assert: Correct throttle returned
        assert throttle == 15

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
            # Act & Assert: Try to set duration should raise exception
            with pytest.raises(Exception, match="Settings save failed"):
                motor_test_model.set_test_duration_s(2.0)

            # Assert: Error was logged
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
            # Act & Assert: Try to set throttle should raise exception
            with pytest.raises(Exception, match="Settings save failed"):
                motor_test_model.set_test_throttle_pct(10)

            # Assert: Error was logged
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
        THEN: Should raise MotorTestSafetyError with appropriate message
        """
        # Arrange: Mock flight controller as connected but battery status unavailable
        motor_test_model.flight_controller.master = MagicMock()
        motor_test_model.flight_controller.fc_parameters = {
            "BATT_MONITOR": 4,  # Battery monitoring enabled
        }

        # Mock battery monitor to return unavailable status
        with (
            patch.object(motor_test_model.battery_monitor, "get_voltage_status", return_value="unavailable"),
            pytest.raises(MotorTestSafetyError, match=r"Could not read battery status"),
        ):
            # Act: Check safety should raise MotorTestSafetyError
            motor_test_model.is_motor_test_safe()


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

    def test_frame_options_skip_layouts_missing_required_fields(self, motor_test_model, caplog) -> None:
        """
        Layouts without names are skipped with a warning.

        GIVEN: A layout entry lacking a ClassName/TypeName pair
        WHEN: The model reloads frame options
        THEN: The entry is ignored and a warning is logged
        """
        broken_layout = {"Class": 9, "Type": 9, "motors": []}
        motor_test_model._motor_data_loader.data["layouts"].append(broken_layout)  # pylint: disable=protected-access
        motor_test_model._cached_frame_options = None  # pylint: disable=protected-access

        with caplog.at_level("WARNING"):
            frame_options = motor_test_model.get_frame_options()

        assert "Skipping motor layout" in caplog.text
        assert "QUAD" in frame_options  # Existing healthy entries remain
        assert 9 not in frame_options.get("", {})

    def test_frame_options_warn_when_no_sources_available(self, motor_test_model, caplog) -> None:
        """
        The user sees a warning if neither motor data nor metadata provide options.

        GIVEN: Missing JSON data and empty metadata
        WHEN: The UI requests frame options
        THEN: The model returns an empty dict and logs a warning
        """
        motor_test_model._motor_data_loader.data = None  # pylint: disable=protected-access
        motor_test_model._cached_frame_options = None  # pylint: disable=protected-access
        motor_test_model.filesystem.doc_dict = {}

        with caplog.at_level("WARNING"):
            options = motor_test_model.get_frame_options()

        assert options == {}
        assert "No frame options" in caplog.text

    def test_frame_options_use_metadata_when_json_entries_invalid(self, motor_test_model) -> None:
        """
        Invalid JSON layouts fall back to the parameter metadata catalog.

        GIVEN: Layout entries missing required fields
        WHEN: The model rebuilds the frame options
        THEN: It loads values from doc_dict instead
        """
        motor_test_model._motor_data_loader.data = {"layouts": [{"Class": 7}]}  # pylint: disable=protected-access
        motor_test_model._cached_frame_options = None  # pylint: disable=protected-access

        options = motor_test_model.get_frame_options()

        assert "QUAD" in options

    def test_frame_options_fallback_uses_doc_dict_values(self, motor_test_model) -> None:
        """When JSON layouts are empty the model rebuilds options from doc_dict."""
        motor_test_model._motor_data_loader.data = {"layouts": []}  # pylint: disable=protected-access
        motor_test_model._cached_frame_options = None  # pylint: disable=protected-access
        motor_test_model.filesystem.doc_dict = {
            "FRAME_TYPE": {
                "values": {
                    "42": "TEST: CUSTOM",
                }
            }
        }

        options = motor_test_model.get_frame_options()

        assert options == {"TEST": {42: "CUSTOM"}}

    def test_frame_options_fallback_skips_invalid_doc_entries(self, motor_test_model) -> None:
        """Fallback processing skips entries with missing codes, delimiters, or bad numbers."""
        motor_test_model._motor_data_loader.data = {"layouts": []}  # pylint: disable=protected-access
        motor_test_model._cached_frame_options = None  # pylint: disable=protected-access
        motor_test_model.filesystem.doc_dict = {
            "FRAME_TYPE": {
                "values": {
                    None: "IGNORED",
                    "abc": "BROKEN",
                    "7": "MISSINGDELIM",
                    "8": "VALID: FRAME",
                }
            }
        }

        options = motor_test_model.get_frame_options()

        assert options == {"VALID": {8: "FRAME"}}

    def test_frame_options_fallback_handles_missing_frame_type_section(self, motor_test_model) -> None:
        """If FRAME_TYPE metadata is absent the fallback returns an empty dict without crashing."""
        motor_test_model._motor_data_loader.data = {"layouts": []}  # pylint: disable=protected-access
        motor_test_model._cached_frame_options = None  # pylint: disable=protected-access
        motor_test_model.filesystem.doc_dict = {"FRAME_CLASS": {"values": {"1": "Quad"}}}

        assert motor_test_model.get_frame_options() == {}


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
            motor_test_model.set_test_duration_s(duration)

            # Assert: Setting saved successfully (no exception raised)
            mock_set.assert_called_once_with("motor_test/duration", duration)


class TestMotorTestDataModelSettingsGuards:
    """Test guard rails applied to stored settings."""

    def test_user_cannot_save_duration_below_minimum(self, motor_test_model) -> None:
        """
        Duration values below 1 second raise ValueError and log an error.

        GIVEN: A user enters 0 seconds
        WHEN: They save the setting
        THEN: ValidationError is raised and the error is logged
        """
        with (
            patch("ardupilot_methodic_configurator.data_model_motor_test.logging_error") as mock_log,
            pytest.raises(ValueError, match="at least"),
        ):
            motor_test_model.set_test_duration_s(0)

        assert mock_log.call_count == 1

    def test_user_cannot_save_duration_above_maximum(self, motor_test_model) -> None:
        """Duration values above 60 seconds are rejected with a helpful message."""
        with (
            patch("ardupilot_methodic_configurator.data_model_motor_test.logging_error") as mock_log,
            pytest.raises(ValueError, match="must not exceed"),
        ):
            motor_test_model.set_test_duration_s(120)

        assert mock_log.call_count == 1

    def test_user_cannot_save_throttle_below_minimum(self, motor_test_model) -> None:
        """Throttle percentages below 1% are invalid."""
        with (
            patch("ardupilot_methodic_configurator.data_model_motor_test.logging_error") as mock_log,
            pytest.raises(ValueError, match="at least"),
        ):
            motor_test_model.set_test_throttle_pct(0)

        assert mock_log.call_count == 1

    def test_user_cannot_save_throttle_above_maximum(self, motor_test_model) -> None:
        """Throttle percentages above 100% trigger an error message."""
        with (
            patch("ardupilot_methodic_configurator.data_model_motor_test.logging_error") as mock_log,
            pytest.raises(ValueError, match="must not exceed"),
        ):
            motor_test_model.set_test_throttle_pct(150)

        assert mock_log.call_count == 1


class TestMotorTestDataModelSettingsEdgeCases:
    """Test initialization edge cases for persisted settings."""

    @staticmethod
    def _build_model(
        mock_flight_controller: FlightController,
        mock_filesystem: LocalFilesystem,
        mock_motor_data_json: dict[str, object],
    ) -> MotorTestDataModel:
        with patch("ardupilot_methodic_configurator.data_model_motor_test.FilesystemJSONWithSchema") as loader_cls:
            loader = MagicMock()
            loader.load_json_data.return_value = mock_motor_data_json
            loader.data = mock_motor_data_json
            loader_cls.return_value = loader
            return MotorTestDataModel(mock_flight_controller, mock_filesystem)

    def test_user_is_warned_when_duration_setting_missing(
        self,
        mock_flight_controller,
        mock_filesystem,
        mock_motor_data_json,
        monkeypatch,
    ) -> None:
        """Missing duration settings raise a ReferenceError during initialization."""

        def fake_get(setting: str) -> Optional[float]:
            if setting == "motor_test/duration":
                return None
            if setting == "motor_test/throttle_pct":
                return 12
            return 0

        monkeypatch.setattr(
            "ardupilot_methodic_configurator.data_model_motor_test.ProgramSettings.get_setting",
            fake_get,
        )

        with (
            patch("ardupilot_methodic_configurator.data_model_motor_test.logging_error") as mock_log,
            pytest.raises(ReferenceError, match="duration setting not found"),
        ):
            self._build_model(mock_flight_controller, mock_filesystem, mock_motor_data_json)

        assert mock_log.call_count == 1

    def test_user_is_warned_when_duration_setting_out_of_range(
        self,
        mock_flight_controller,
        mock_filesystem,
        mock_motor_data_json,
        monkeypatch,
    ) -> None:
        """Out-of-range duration values raise ValueError on load."""

        def fake_get(setting: str) -> Optional[float]:
            if setting == "motor_test/duration":
                return 0
            if setting == "motor_test/throttle_pct":
                return 12
            return 0

        monkeypatch.setattr(
            "ardupilot_methodic_configurator.data_model_motor_test.ProgramSettings.get_setting",
            fake_get,
        )

        with pytest.raises(ValueError, match="at least"):
            self._build_model(mock_flight_controller, mock_filesystem, mock_motor_data_json)

    def test_user_is_warned_when_throttle_setting_missing(
        self,
        mock_flight_controller,
        mock_filesystem,
        mock_motor_data_json,
        monkeypatch,
    ) -> None:
        """Missing throttle percentages raise ReferenceError."""

        def fake_get(setting: str) -> Optional[float]:
            if setting == "motor_test/throttle_pct":
                return None
            if setting == "motor_test/duration":
                return 5
            return 0

        monkeypatch.setattr(
            "ardupilot_methodic_configurator.data_model_motor_test.ProgramSettings.get_setting",
            fake_get,
        )

        with (
            patch("ardupilot_methodic_configurator.data_model_motor_test.logging_error") as mock_log,
            pytest.raises(ReferenceError, match="throttle percentage setting not found"),
        ):
            self._build_model(mock_flight_controller, mock_filesystem, mock_motor_data_json)

        assert mock_log.call_count == 1

    def test_user_is_warned_when_throttle_setting_out_of_range(
        self,
        mock_flight_controller,
        mock_filesystem,
        mock_motor_data_json,
        monkeypatch,
    ) -> None:
        """Throttle percentages outside 1-100 are rejected on load."""

        def fake_get(setting: str) -> Optional[float]:
            if setting == "motor_test/throttle_pct":
                return 500
            if setting == "motor_test/duration":
                return 5
            return 0

        monkeypatch.setattr(
            "ardupilot_methodic_configurator.data_model_motor_test.ProgramSettings.get_setting",
            fake_get,
        )

        with pytest.raises(ValueError, match="must not exceed"):
            self._build_model(mock_flight_controller, mock_filesystem, mock_motor_data_json)

    def test_user_is_warned_when_duration_setting_above_maximum(
        self,
        mock_flight_controller,
        mock_filesystem,
        mock_motor_data_json,
        monkeypatch,
    ) -> None:
        """Duration settings above 60 seconds raise ValueError on load."""

        def fake_get(setting: str) -> Optional[float]:
            if setting == "motor_test/duration":
                return 999
            if setting == "motor_test/throttle_pct":
                return 12
            return 0

        monkeypatch.setattr(
            "ardupilot_methodic_configurator.data_model_motor_test.ProgramSettings.get_setting",
            fake_get,
        )

        with pytest.raises(ValueError, match="must not exceed"):
            self._build_model(mock_flight_controller, mock_filesystem, mock_motor_data_json)

    def test_user_is_warned_when_throttle_setting_below_minimum(
        self,
        mock_flight_controller,
        mock_filesystem,
        mock_motor_data_json,
        monkeypatch,
    ) -> None:
        """Throttle settings below 1% are rejected."""

        def fake_get(setting: str) -> Optional[float]:
            if setting == "motor_test/throttle_pct":
                return 0
            if setting == "motor_test/duration":
                return 5
            return 0

        monkeypatch.setattr(
            "ardupilot_methodic_configurator.data_model_motor_test.ProgramSettings.get_setting",
            fake_get,
        )

        with pytest.raises(ValueError, match="at least"):
            self._build_model(mock_flight_controller, mock_filesystem, mock_motor_data_json)

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
            motor_test_model.set_test_throttle_pct(throttle)

            # Assert: Setting saved successfully (no exception raised)
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

            # Act & Assert: Try to save test duration should raise exception
            with pytest.raises(Exception, match="Settings error"):
                motor_test_model.set_test_duration_s(2.0)

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

            # Act & Assert: Try to save test throttle should raise exception
            with pytest.raises(Exception, match="Settings error"):
                motor_test_model.set_test_throttle_pct(50)

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


class TestMotorTestDataModelFrameSelectionWorkflows:  # pylint: disable=too-many-public-methods
    """Test high-level frame selection and combo-box workflows."""

    def test_user_refreshes_frame_configuration_when_layout_unchanged(self, motor_test_model) -> None:
        """
        Re-reading the same frame configuration keeps the UI responsive.

        GIVEN: A connected controller that already shared its frame layout
        WHEN: The user refreshes the configuration twice without making changes
        THEN: The model should report success each time without recomputing the layout
        """
        motor_test_model.flight_controller.get_frame_info.reset_mock()

        assert motor_test_model.refresh_from_flight_controller() is True
        assert motor_test_model.refresh_from_flight_controller() is True
        assert motor_test_model.flight_controller.get_frame_info.call_count >= 2

    def test_user_is_informed_when_controller_reports_unknown_frame(self, motor_test_model, caplog) -> None:
        """
        Unsupported frame combinations surface a clear warning to the user.

        GIVEN: The flight controller reports a frame class/type with no known layout
        WHEN: The user refreshes the configuration summary
        THEN: The model should return False so the UI can highlight the issue
        """
        motor_test_model.flight_controller.get_frame_info.return_value = (9, 9)

        with caplog.at_level("ERROR"):
            assert motor_test_model.refresh_from_flight_controller() is False

        assert "No motor configuration found" in caplog.text
        assert motor_test_model.motor_count == 0

    def test_user_updates_frame_type_from_dropdown_text(self, motor_test_model) -> None:
        """
        Selecting a new entry from the frame type list uploads the matching parameters.

        GIVEN: A user browsing available QUAD layouts
        WHEN: They pick the "PLUS" entry from the dropdown list
        THEN: The data model uploads FRAME_TYPE and updates its cached layout
        """
        original_method = motor_test_model.set_parameter
        with patch.object(motor_test_model, "set_parameter", wraps=original_method) as spy:
            assert motor_test_model.update_frame_type_from_selection("PLUS") is True

        spy.assert_called()
        assert motor_test_model.frame_type == 0

    def test_user_updates_frame_type_using_combobox_key(self, motor_test_model) -> None:
        """
        Selecting by encoded key keeps the UI combobox and the model in sync.

        GIVEN: A user interacts with a PairTupleCombobox showing motor layouts
        WHEN: They choose the option with key "0"
        THEN: The model should map the key back to the proper layout and update itself
        """
        motor_test_model._frame_type = 1  # pylint: disable=protected-access
        motor_test_model.flight_controller.fc_parameters["FRAME_TYPE"] = 1

        assert motor_test_model.update_frame_type_by_key("0") is True
        assert motor_test_model.frame_type == 0

    def test_frame_type_selection_skips_redundant_uploads(self, motor_test_model) -> None:
        """Selecting the already-active layout avoids unnecessary parameter writes."""
        motor_test_model._frame_class = 1  # pylint: disable=protected-access
        motor_test_model._frame_type = 0  # pylint: disable=protected-access
        motor_test_model.flight_controller.fc_parameters["FRAME_CLASS"] = 1
        motor_test_model.flight_controller.fc_parameters["FRAME_TYPE"] = 0

        with patch.object(motor_test_model, "set_parameter") as mock_set_param:
            assert motor_test_model.update_frame_type_from_selection("PLUS") is True

        mock_set_param.assert_not_called()

    def test_frame_type_selection_handles_missing_layout_data(self, motor_test_model) -> None:
        """When layout metadata is absent the selection still succeeds with zero motors."""
        # Provide minimal layout with PLUS type but no motors
        motor_test_model._motor_data_loader.data = {  # pylint: disable=protected-access
            "layouts": [{"Class": 1, "ClassName": "QUAD", "Type": 0, "TypeName": "PLUS", "motors": []}]
        }
        motor_test_model._frame_class = 1  # pylint: disable=protected-access
        motor_test_model._frame_type = 3  # pylint: disable=protected-access

        with patch.object(motor_test_model, "set_parameter", return_value=None):
            assert motor_test_model.update_frame_type_from_selection("PLUS") is True

        assert motor_test_model.motor_count == 0

    def test_frame_type_selection_wraps_unexpected_errors(self, motor_test_model) -> None:
        """Unexpected errors while uploading parameters raise FrameConfigurationError."""
        with (
            patch.object(motor_test_model, "set_parameter", side_effect=RuntimeError("upload boom")),
            pytest.raises(FrameConfigurationError, match="Failed to update frame configuration"),
        ):
            motor_test_model.update_frame_type_from_selection("PLUS")

    def test_frame_type_selection_without_matching_layout(self, motor_test_model) -> None:
        """Non-matching layouts leave the motor count at zero after selection."""
        # Provide PLUS type for class 1 (current) but with a different class layout (class 9)
        motor_test_model._motor_data_loader.data = {  # pylint: disable=protected-access
            "layouts": [
                {"Class": 1, "ClassName": "QUAD", "Type": 0, "TypeName": "PLUS", "motors": []},
                {"Class": 9, "Type": 9, "motors": []},
            ]
        }

        with patch.object(motor_test_model, "set_parameter", return_value=None):
            assert motor_test_model.update_frame_type_from_selection("PLUS") is True

        assert motor_test_model.motor_count == 0

    def test_frame_type_selection_propagates_parameter_errors(self, motor_test_model) -> None:
        """ParameterError raised during upload is re-raised unchanged."""
        with (
            patch.object(motor_test_model, "set_parameter", side_effect=ParameterError("upload failed")),
            pytest.raises(ParameterError, match="upload failed"),
        ):
            motor_test_model.update_frame_type_from_selection("PLUS")

    def test_invalid_frame_type_key_is_rejected(self, motor_test_model) -> None:
        """
        Invalid combobox keys raise user-friendly validation errors.

        GIVEN: A user types an invalid frame type identifier
        WHEN: The combobox tries to convert the key into a frame update
        THEN: The model raises ValidationError so the UI can show feedback
        """
        with pytest.raises(ValidationError, match="Invalid frame type selection"):
            motor_test_model.update_frame_type_by_key("not-a-number")

    def test_user_can_parse_frame_type_text_selection(self, motor_test_model) -> None:
        """
        Parsing the dropdown text yields numeric class and type codes.

        GIVEN: The UI shows human-readable type names
        WHEN: The user selects the QUAD PLUS entry
        THEN: The model resolves it back to the ArduPilot class/type codes
        """
        frame_class_code, frame_type_code = motor_test_model.parse_frame_type_selection("PLUS")

        assert frame_class_code == 1
        assert frame_type_code == 0

    def test_user_gets_validation_error_for_unknown_frame_text(self, motor_test_model) -> None:
        """
        Unknown frame descriptions raise validation errors instead of misconfiguring the FC.

        GIVEN: A mistyped frame description
        WHEN: The model attempts to parse it
        THEN: ValidationError explains that the selection does not exist
        """
        with pytest.raises(ValidationError, match="Could not find frame type"):
            motor_test_model.parse_frame_type_selection("Imaginary Frame")

    def test_user_inspects_current_frame_type_metadata(self, motor_test_model) -> None:
        """
        The combo-box helper APIs expose current selections and available options.

        GIVEN: A quad X frame loaded from the controller
        WHEN: The UI asks for selection text, key, and pair tuples
        THEN: The model returns matching values for the widgets
        """
        selection_text = motor_test_model.get_current_frame_selection_text()
        selection_key = motor_test_model.get_current_frame_selection_key()
        selection_pairs = motor_test_model.get_frame_type_pairs()

        assert selection_text == "X"
        assert selection_key == "1"
        assert ("1", "1: X") in selection_pairs

    def test_user_reads_available_frame_types_for_current_class(self, motor_test_model) -> None:
        """
        Users can request only the frame types that belong to the currently connected frame class.

        GIVEN: A connected controller reporting frame class 1 (QUAD)
        WHEN: The model fetches types for that class
        THEN: It should return both PLUS and X entries
        """
        types = motor_test_model.get_current_frame_class_types()

        assert types[0] == "PLUS"
        assert types[1] == "X"

        motor_test_model.flight_controller.fc_parameters["FRAME_CLASS"] = 99
        assert motor_test_model.get_current_frame_class_types() == {}

    def test_user_reuses_cached_frame_options_after_first_load(self, motor_test_model) -> None:
        """
        Frame option loading hits disk only once and relies on caching afterwards.

        GIVEN: The model already parsed the JSON layouts
        WHEN: The user asks for the options again later
        THEN: The cached result is returned even if the loader data changes
        """
        first_result = motor_test_model.get_frame_options()
        motor_test_model._motor_data_loader.data = {}  # pylint: disable=protected-access
        cached_result = motor_test_model.get_frame_options()

        assert cached_result == first_result
        assert "QUAD" in cached_result

    def test_user_falls_back_to_parameter_metadata_when_layouts_missing(self, motor_test_model) -> None:
        """
        Missing motor layout files still produce options via parameter metadata.

        GIVEN: The AP_Motors JSON data is unavailable
        WHEN: The user opens the frame type picker
        THEN: The model derives options from the filesystem doc_dict fallback
        """
        motor_test_model._motor_data_loader.data = {}  # pylint: disable=protected-access
        motor_test_model._cached_frame_options = None  # pylint: disable=protected-access

        options = motor_test_model.get_frame_options()

        assert "QUAD" in options
        assert options["QUAD"][0] == "PLUS"

    def test_user_receives_error_when_requesting_invalid_motor_order(self, motor_test_model) -> None:
        """
        Asking for test order of a non-existent motor returns a clear ValueError.

        GIVEN: A quad layout with four motors
        WHEN: The UI queries the order for motor 99
        THEN: The model raises ValueError describing the invalid request
        """
        with pytest.raises(ValueError, match="Invalid motor number"):
            motor_test_model.test_order(99)

    def test_user_observes_double_letter_labels_for_large_layout(self, motor_test_model) -> None:
        """
        Frame labels extend beyond Z for very large motor counts.

        GIVEN: A layout describing 27 motors
        WHEN: The controller reports that layout
        THEN: The model generates AA for the 27th motor label
        """
        mega_layout = {
            "Class": 2,
            "ClassName": "MEGA",
            "Type": 3,
            "TypeName": "GRID",
            "motors": [{"Number": idx, "TestOrder": idx, "Rotation": "CCW"} for idx in range(1, 28)],
        }
        motor_test_model._motor_data_loader.data["layouts"].append(mega_layout)  # pylint: disable=protected-access
        motor_test_model.flight_controller.get_frame_info.return_value = (2, 3)
        motor_test_model.flight_controller.fc_parameters["FRAME_CLASS"] = 2
        motor_test_model.flight_controller.fc_parameters["FRAME_TYPE"] = 3

        assert motor_test_model.refresh_from_flight_controller() is True
        assert motor_test_model.motor_labels[0] == "A"
        assert motor_test_model.motor_labels[26] == "AA"
        assert motor_test_model.motor_numbers[26] == 27

    def test_user_reads_motor_test_order_for_existing_motor(self, motor_test_model) -> None:
        """
        Requesting the test order for a valid motor returns a zero-based index.

        GIVEN: The default QUAD X layout
        WHEN: The UI asks for the order of motor 1
        THEN: The model reports zero because that motor is first in sequence
        """
        assert motor_test_model.test_order(1) == 0

    def test_user_is_warned_when_frame_types_requested_without_connection(self, motor_test_model, caplog) -> None:
        """
        Connection loss prevents listing frame types.

        GIVEN: A disconnected controller
        WHEN: The UI requests available types
        THEN: An empty dict is returned and a warning is logged
        """
        motor_test_model.flight_controller.master = None

        with caplog.at_level("WARNING"):
            assert motor_test_model.get_current_frame_class_types() == {}

        assert "connection required" in caplog.text

    def test_user_is_warned_when_frame_class_parameter_missing(self, motor_test_model, caplog) -> None:
        """
        Missing FRAME_CLASS metadata surfaces a warning.

        GIVEN: Connected hardware without FRAME_CLASS parameter
        WHEN: The model tries to read available types
        THEN: It returns an empty dict and logs the problem
        """
        motor_test_model.flight_controller.fc_parameters.pop("FRAME_CLASS", None)

        with caplog.at_level("WARNING"):
            assert motor_test_model.get_current_frame_class_types() == {}

        assert "FRAME_CLASS parameter not found" in caplog.text

    def test_user_cannot_parse_frame_type_when_controller_disconnected(self, motor_test_model) -> None:
        """
        Parsing selections requires an active connection.

        GIVEN: The controller disconnects mid-session
        WHEN: The UI tries to resolve a dropdown entry
        THEN: ValidationError explains that the connection is required
        """
        motor_test_model.flight_controller.master = None

        with pytest.raises(ValidationError, match="connection required"):
            motor_test_model.parse_frame_type_selection("PLUS")

    def test_user_cannot_parse_frame_type_when_frame_class_missing(self, motor_test_model) -> None:
        """
        FRAME_CLASS metadata must exist to parse selections.

        GIVEN: The FC parameters suddenly omit FRAME_CLASS
        WHEN: The UI requests parsing
        THEN: ValidationError references the missing parameter
        """
        motor_test_model.flight_controller.fc_parameters.pop("FRAME_CLASS", None)

        with pytest.raises(ValidationError, match="FRAME_CLASS parameter not found"):
            motor_test_model.parse_frame_type_selection("PLUS")

    def test_user_cannot_parse_frame_type_when_frame_class_non_numeric(self, motor_test_model) -> None:
        """
        Garbage data in FRAME_CLASS triggers a parsing error.

        GIVEN: A FRAME_CLASS string that is not numeric
        WHEN: The user parses a selection
        THEN: ValidationError reports the conversion failure
        """
        motor_test_model.flight_controller.fc_parameters["FRAME_CLASS"] = "abc"

        with pytest.raises(ValidationError, match="Error parsing frame type"):
            motor_test_model.parse_frame_type_selection("PLUS")

    def test_user_synchronizes_frame_class_when_model_state_outdated(self, motor_test_model) -> None:
        """
        The model uploads FRAME_CLASS when its cached value drifts from the controller.

        GIVEN: The cached state was stale after offline edits
        WHEN: The user selects the current frame type again
        THEN: FRAME_CLASS and FRAME_TYPE parameters are both updated if necessary
        """
        motor_test_model._frame_class = 99  # pylint: disable=protected-access
        motor_test_model.flight_controller.set_param.reset_mock()

        motor_test_model.update_frame_type_from_selection("PLUS")

        param_names = [call.args[0] for call in motor_test_model.flight_controller.set_param.call_args_list]
        assert "FRAME_CLASS" in param_names
        assert "FRAME_TYPE" in param_names

    def test_user_is_warned_when_combobox_key_missing_for_current_class(self, motor_test_model) -> None:
        """
        Integer keys outside the available set raise ValidationError.

        GIVEN: Only PLUS and X layout keys exist
        WHEN: The UI sends key 99
        THEN: The model raises ValidationError noting the missing option
        """
        with pytest.raises(ValidationError, match="not available"):
            motor_test_model.update_frame_type_by_key("99")

    def test_user_updates_frame_configuration_and_motor_count_recomputes(self, motor_test_model) -> None:
        """
        Frame updates recompute the cached motor count and layout metadata.

        GIVEN: Stale frame class/type information
        WHEN: The user requests a refresh using update_frame_configuration
        THEN: The motor count matches the selected layout
        """
        motor_test_model._frame_class = 2  # pylint: disable=protected-access
        motor_test_model._frame_type = 99  # pylint: disable=protected-access

        motor_test_model.update_frame_configuration(1, 1)

        assert motor_test_model.motor_count == 4

    def test_layout_entries_without_test_order_are_skipped(self, motor_test_model) -> None:
        """
        Motors lacking TestOrder metadata leave their slots empty.

        GIVEN: A layout where the first motor has no TestOrder field
        WHEN: The controller reports that layout
        THEN: The corresponding entry in motor_numbers remains zero while valid entries populate
        """
        sparse_layout = {
            "Class": 4,
            "ClassName": "DUAL",
            "Type": 1,
            "TypeName": "SKIP",
            "motors": [
                {"Number": 1, "Rotation": "CCW"},
                {"Number": 2, "TestOrder": 1, "Rotation": "CW"},
            ],
        }
        motor_test_model._motor_data_loader.data["layouts"].append(sparse_layout)  # pylint: disable=protected-access
        motor_test_model.flight_controller.get_frame_info.return_value = (4, 1)
        motor_test_model.flight_controller.fc_parameters["FRAME_CLASS"] = 4
        motor_test_model.flight_controller.fc_parameters["FRAME_TYPE"] = 1

        assert motor_test_model.refresh_from_flight_controller() is True
        assert motor_test_model.motor_numbers[1] == 0
        assert motor_test_model.motor_numbers[0] == 2


class TestMotorTestDataModelBatteryFeedback:
    """Test user-facing battery indicators and warning strings."""

    def test_user_sees_cached_battery_status_after_initial_request(self, motor_test_model) -> None:
        """
        Battery polling stops after the first successful response to avoid spamming the FC.

        GIVEN: Battery monitoring returns a "warming up" message before providing measurements
        WHEN: The model polls multiple times
        THEN: It should request streaming twice and reuse cached data afterwards
        """
        motor_test_model.flight_controller.request_periodic_battery_status.reset_mock()
        motor_test_model.flight_controller.get_battery_status.side_effect = [
            ((12.3, 2.0), "priming"),
            ((12.5, 2.1), ""),
            ((12.5, 2.1), ""),
        ]

        motor_test_model.get_battery_status()
        motor_test_model.get_battery_status()
        motor_test_model.get_battery_status()

        assert motor_test_model.flight_controller.request_periodic_battery_status.call_count == 2

    def test_user_gets_color_coded_voltage_feedback(self, motor_test_model) -> None:
        """
        Voltage status is translated into colors for the battery indicator widget.

        GIVEN: Live voltage data from the controller
        WHEN: The user checks the indicator
        THEN: The model reports green, red, gray, or orange depending on the status
        """
        assert motor_test_model.get_battery_status_color() == "green"

        motor_test_model.flight_controller.get_battery_status.return_value = ((10.0, 2.0), "")
        assert motor_test_model.get_battery_status_color() == "red"

        motor_test_model.flight_controller.is_battery_monitoring_enabled.return_value = False
        assert motor_test_model.get_battery_status_color() == "gray"

        motor_test_model.flight_controller.is_battery_monitoring_enabled.return_value = True
        with patch.object(motor_test_model, "get_voltage_status", return_value="low"):
            assert motor_test_model.get_battery_status_color() == "orange"

    def test_user_reads_battery_display_text_feedback(self, motor_test_model) -> None:
        """
        The UI strings clearly communicate whether telemetry is disabled, unavailable, or healthy.

        GIVEN: Various monitoring states
        WHEN: The UI asks for the formatted voltage/current strings
        THEN: The model returns context-aware messages
        """
        motor_test_model.flight_controller.is_battery_monitoring_enabled.return_value = False
        assert motor_test_model.get_battery_display_text() == (_("Voltage: Disabled"), _("Current: Disabled"))

        motor_test_model.flight_controller.is_battery_monitoring_enabled.return_value = True
        motor_test_model.flight_controller.get_battery_status.return_value = (None, "")
        assert motor_test_model.get_battery_display_text() == (_("Voltage: N/A"), _("Current: N/A"))

        motor_test_model.flight_controller.get_battery_status.return_value = ((12.34, 1.98), "")
        voltage_text, current_text = motor_test_model.get_battery_display_text()

        assert "12.34" in voltage_text
        assert "1.98" in current_text

    def test_battery_safety_messaging_highlights_reason(self, motor_test_model) -> None:
        """
        Safety dialogs provide actionable text and remember acknowledgement state.

        GIVEN: A user reviewing the first-test warning and a battery error reason
        WHEN: They acknowledge the warning and inspect the helper text
        THEN: The warning state sticks and the reason string is interpolated into the copy
        """
        assert motor_test_model.should_show_first_test_warning() is True
        warning_message = motor_test_model.get_safety_warning_message()
        assert "IMPORTANT SAFETY WARNING" in warning_message

        battery_message = motor_test_model.get_battery_safety_message("Voltage too low")
        assert "Voltage too low" in battery_message

        assert motor_test_model.is_battery_related_safety_issue("Voltage too low") is True
        assert motor_test_model.is_battery_related_safety_issue("Motor stalled") is False

        motor_test_model.acknowledge_first_test_warning()
        assert motor_test_model.should_show_first_test_warning() is False


class TestMotorTestDataModelParameterGuards:
    """Test parameter guard rails and reboot requirements."""

    def test_user_triggers_reboot_for_parameters_marked_as_reboot_required(self, motor_test_model) -> None:
        """
        Parameters that require a reboot schedule one automatically after a successful upload.

        GIVEN: MOT_SPIN_ARM metadata stating that a reboot is required
        WHEN: The user sets a new value within the allowed range
        THEN: The model calls reset_and_reconnect so the FC applies the change
        """
        motor_test_model.flight_controller.reset_and_reconnect = MagicMock()

        motor_test_model.set_parameter("MOT_SPIN_ARM", 0.08)

        motor_test_model.flight_controller.reset_and_reconnect.assert_called_once()

    def test_user_cannot_set_parameter_outside_documented_bounds(self, motor_test_model) -> None:
        """
        Documentation-derived bounds guard against impossible parameter values.

        GIVEN: Metadata describing the valid MOT_SPIN_ARM range
        WHEN: The user enters values outside that range
        THEN: ValidationError explains why the update is rejected
        """
        with pytest.raises(ValidationError, match="smaller than"):
            motor_test_model.set_parameter("MOT_SPIN_ARM", 0.01)

        with pytest.raises(ValidationError, match="greater than"):
            motor_test_model.set_parameter("MOT_SPIN_ARM", 0.9)

    def test_user_cannot_raise_spin_arm_above_spin_min_margin(self, motor_test_model) -> None:
        """
        MOT_SPIN_ARM must stay at least 0.02 below MOT_SPIN_MIN.

        GIVEN: A configured spin minimum of 0.12
        WHEN: The user tries to set spin arm to 0.11
        THEN: ValidationError reminds them about the 0.02 guard band
        """
        motor_test_model.flight_controller.fc_parameters["MOT_SPIN_MIN"] = 0.12

        with pytest.raises(ValidationError, match=r"0\.02 below"):
            motor_test_model.set_motor_spin_arm_value(0.11)

    def test_user_cannot_lower_spin_min_without_spin_arm_value(self, motor_test_model) -> None:
        """
        MOT_SPIN_MIN updates require a known MOT_SPIN_ARM baseline.

        GIVEN: Missing MOT_SPIN_ARM telemetry
        WHEN: The user attempts to set MOT_SPIN_MIN
        THEN: ParameterError explains why the update is unsafe
        """
        motor_test_model.flight_controller.fc_parameters.pop("MOT_SPIN_ARM", None)

        with pytest.raises(ParameterError, match="must be available"):
            motor_test_model.set_motor_spin_min_value(0.20)

    def test_user_cannot_set_spin_min_too_close_to_spin_arm(self, motor_test_model) -> None:
        """
        The 0.02 guard applies to MOT_SPIN_MIN as well.

        GIVEN: MOT_SPIN_ARM at 0.15
        WHEN: The user sets MOT_SPIN_MIN to 0.16
        THEN: ValidationError warns about the insufficient gap
        """
        motor_test_model.flight_controller.fc_parameters["MOT_SPIN_ARM"] = 0.15

        with pytest.raises(ValidationError, match=r"0\.02 higher"):
            motor_test_model.set_motor_spin_min_value(0.16)

    def test_user_sets_spin_arm_value_within_safe_margin(self, motor_test_model) -> None:
        """Valid spin arm updates delegate to the generic parameter setter."""
        motor_test_model.flight_controller.set_param.reset_mock()

        motor_test_model.set_motor_spin_arm_value(0.08)

        motor_test_model.flight_controller.set_param.assert_called_with("MOT_SPIN_ARM", 0.08)

    def test_user_sets_spin_min_value_within_safe_margin(self, motor_test_model) -> None:
        """Valid spin minimum updates also leverage the shared setter path."""
        motor_test_model.flight_controller.set_param.reset_mock()

        motor_test_model.set_motor_spin_min_value(0.15)

        motor_test_model.flight_controller.set_param.assert_called_with("MOT_SPIN_MIN", 0.15)


class TestMotorTestDataModelMotorExecutionWorkflows:
    """Exercise single, all, sequential, and emergency motor test workflows."""

    def test_user_cannot_request_mismatched_motor_output(self, motor_test_model) -> None:
        """
        The UI validates that the selected motor output matches the expected test order.

        GIVEN: A quad where motor 1 is first in the sequence
        WHEN: The user selects sequence 0 but output 2
        THEN: ValidationError explains the mismatch
        """
        with (
            patch.object(motor_test_model, "is_motor_test_safe", return_value=None),
            pytest.raises(ValidationError, match="expected: 1"),
        ):
            motor_test_model.test_motor(0, 2, 10, 2)

    def test_user_cannot_request_duration_shorter_or_longer_than_limits(self, motor_test_model) -> None:
        """
        Test duration bounds prevent dangerous commands.

        GIVEN: The duration range of 1-60 seconds
        WHEN: The user enters 0 seconds or 120 seconds
        THEN: ValidationError is raised in both cases
        """
        with patch.object(motor_test_model, "is_motor_test_safe", return_value=None):
            with pytest.raises(ValidationError, match=r"valid range:\s*1-60"):
                motor_test_model.test_motor(0, 1, 10, 0)
            with pytest.raises(ValidationError, match=r"valid range:\s*1-60"):
                motor_test_model.test_motor(0, 1, 10, 120)

    def test_motor_command_failure_surfaces_execution_error(self, motor_test_model) -> None:
        """
        Backend failures bubble up as MotorTestExecutionError for the UI to display.

        GIVEN: The FC rejects a motor command
        WHEN: The user starts a motor test
        THEN: MotorTestExecutionError carries the backend error string
        """
        motor_test_model.flight_controller.test_motor.return_value = (False, "PWM timeout")

        with (
            patch.object(motor_test_model, "is_motor_test_safe", return_value=None),
            pytest.raises(MotorTestExecutionError, match="PWM timeout"),
        ):
            motor_test_model.test_motor(0, 1, 10, 2)

    def test_status_callbacks_receive_events_for_each_workflow(self, motor_test_model) -> None:
        """
        Status callbacks fire for single, all, sequential, and emergency stop workflows.

        GIVEN: A listener interested in motor status events
        WHEN: The user runs the full workflow suite
        THEN: The callback receives COMMAND_SENT/STOP_SENT events for every motor
        """
        events: list[tuple[int, MotorStatusEvent]] = []

        def _recorder(motor_number: int, event: MotorStatusEvent) -> None:
            events.append((motor_number, event))

        motor_test_model.run_single_motor_test(0, 1, _recorder)
        motor_test_model.run_all_motors_test(_recorder)
        motor_test_model.run_sequential_motor_test(_recorder)
        motor_test_model.emergency_stop_motors(_recorder)

        assert any(event == MotorStatusEvent.COMMAND_SENT for _motor, event in events)
        assert any(event == MotorStatusEvent.STOP_SENT for _motor, event in events)
        assert len(events) >= motor_test_model.motor_count * 3

    def test_stop_all_motors_failure_surfaces_error(self, motor_test_model) -> None:
        """
        Emergency stop failures propagate as MotorTestExecutionError.

        GIVEN: A backend failure when stopping motors
        WHEN: The user presses the stop button
        THEN: MotorTestExecutionError exposes the backend reason
        """
        motor_test_model.flight_controller.stop_all_motors.return_value = (False, "Stop failed")

        with pytest.raises(MotorTestExecutionError, match="Stop failed"):
            motor_test_model.stop_all_motors()

    def test_all_motor_test_failure_surfaces_error(self, motor_test_model) -> None:
        """
        Failed all-motor tests report the FC error code.

        GIVEN: test_all_motors returning False
        WHEN: The user runs the all-motors workflow
        THEN: MotorTestExecutionError is raised
        """
        motor_test_model.flight_controller.test_all_motors.return_value = (False, "All motors failed")

        with pytest.raises(MotorTestExecutionError, match="All motors failed"):
            motor_test_model.test_all_motors(20, 5)

    def test_sequential_motor_test_failure_surfaces_error(self, motor_test_model) -> None:
        """
        Failed sequential tests also raise MotorTestExecutionError.

        GIVEN: test_motors_in_sequence returning False
        WHEN: The user runs the sequential workflow
        THEN: MotorTestExecutionError is raised
        """
        motor_test_model.flight_controller.test_motors_in_sequence.return_value = (False, "Sequence failed")

        with pytest.raises(MotorTestExecutionError, match="Sequence failed"):
            motor_test_model.test_motors_in_sequence(20, 5)

    def test_status_callbacks_are_optional_for_single_motor_runs(self, motor_test_model) -> None:
        """
        Workflows run normally when no listener is registered.

        GIVEN: No status callback provided
        WHEN: The user runs a single motor test
        THEN: The motor command executes without emitting events
        """
        motor_test_model.flight_controller.test_motor.reset_mock()

        motor_test_model.run_single_motor_test(0, 1)

        motor_test_model.flight_controller.test_motor.assert_called_once()


# ==================== Non-Sequential Frame Class Tests ====================


class TestNonSequentialFrameClassMapping:
    """Tests for handling non-sequential frame class numbers like Class 15 SCRIPTINGMATRIX."""

    def test_user_can_select_dotriaconta_frame_class_with_class_15(self, motor_test_model) -> None:
        """
        User selects SCRIPTINGMATRIX frame (class 15) successfully.

        GIVEN: Motor data includes Class 15 (SCRIPTINGMATRIX) with Type 1
        WHEN: Flight controller reports FRAME_CLASS=15
        THEN: Frame types are retrieved correctly for class 15
        """
        # Setup motor data with non-sequential class numbers
        motor_test_model._motor_data_loader.data = {
            "layouts": [
                {"Class": 1, "ClassName": "QUAD", "Type": 0, "TypeName": "PLUS", "motors": []},
                {"Class": 1, "ClassName": "QUAD", "Type": 1, "TypeName": "X", "motors": []},
                {"Class": 15, "ClassName": "SCRIPTINGMATRIX", "Type": 0, "TypeName": "PLUS", "motors": []},
                {"Class": 15, "ClassName": "SCRIPTINGMATRIX", "Type": 1, "TypeName": "DOTRIACONTA/X", "motors": []},
            ]
        }
        motor_test_model.flight_controller.fc_parameters["FRAME_CLASS"] = 15

        # Get types for class 15
        frame_types = motor_test_model.get_current_frame_class_types()

        # Should return both type options for class 15
        assert len(frame_types) == 2
        assert 0 in frame_types
        assert 1 in frame_types
        assert frame_types[0] == "PLUS"
        assert frame_types[1] == "DOTRIACONTA/X"

    def test_user_receives_error_when_selecting_undefined_frame_class(self, motor_test_model) -> None:
        """
        User selecting undefined frame class sees helpful error.

        GIVEN: Motor data with classes 1, 2, 5, 15 (non-sequential)
        WHEN: Flight controller reports FRAME_CLASS=10 (not defined)
        THEN: Warning logged showing max defined class and empty dict returned
        """
        motor_test_model._motor_data_loader.data = {
            "layouts": [
                {"Class": 1, "ClassName": "QUAD", "Type": 0, "TypeName": "PLUS", "motors": []},
                {"Class": 2, "ClassName": "HEXA", "Type": 0, "TypeName": "PLUS", "motors": []},
                {"Class": 5, "ClassName": "Y6", "Type": 0, "TypeName": "default", "motors": []},
                {"Class": 15, "ClassName": "SCRIPTINGMATRIX", "Type": 1, "TypeName": "DOTRIACONTA/X", "motors": []},
            ]
        }
        motor_test_model.flight_controller.fc_parameters["FRAME_CLASS"] = 10

        frame_types = motor_test_model.get_current_frame_class_types()

        assert frame_types == {}

    def test_dotriaconta_32_motors_configuration_loads_correctly(self, motor_test_model) -> None:
        """
        SCRIPTINGMATRIX with 32 motors loads all motor positions.

        GIVEN: Class 15 with 32 motors in JSON data
        WHEN: User configures frame class 15, type 1
        THEN: All 32 motor positions are loaded with correct data
        """
        # Create realistic 32-motor layout
        motors = [
            {"Number": i, "TestOrder": i, "Rotation": "CCW" if i % 2 else "CW", "Roll": 0.0, "Pitch": 0.0}
            for i in range(1, 33)
        ]

        motor_test_model._motor_data_loader.data = {
            "layouts": [
                {"Class": 15, "ClassName": "SCRIPTINGMATRIX", "Type": 1, "TypeName": "DOTRIACONTA/X", "motors": motors}
            ]
        }

        # Update doc_dict to allow FRAME_CLASS=15
        if "FRAME_CLASS" in motor_test_model.filesystem.doc_dict:
            motor_test_model.filesystem.doc_dict["FRAME_CLASS"]["max"] = 15

        motor_test_model.update_frame_configuration(15, 1)

        assert motor_test_model.motor_count == 32
        assert motor_test_model._frame_class == 15
        assert motor_test_model._frame_type == 1

    def test_frame_class_mapping_handles_gaps_in_class_numbers(self, motor_test_model) -> None:
        """
        Frame class mapping works with non-contiguous class numbers.

        GIVEN: Motor data with classes 1, 5, 7, 12, 15 (gaps in sequence)
        WHEN: User queries frame options
        THEN: All classes are accessible by their actual class number
        """
        motor_test_model._motor_data_loader.data = {
            "layouts": [
                {"Class": 1, "ClassName": "QUAD", "Type": 0, "TypeName": "PLUS", "motors": []},
                {"Class": 5, "ClassName": "Y6", "Type": 0, "TypeName": "default", "motors": []},
                {"Class": 7, "ClassName": "TRI", "Type": 0, "TypeName": "default", "motors": []},
                {"Class": 12, "ClassName": "DODECAHEXA", "Type": 0, "TypeName": "PLUS", "motors": []},
                {"Class": 15, "ClassName": "SCRIPTINGMATRIX", "Type": 1, "TypeName": "DOTRIACONTA/X", "motors": []},
            ]
        }

        # Test each class can be accessed
        for class_num in [1, 5, 7, 12, 15]:
            motor_test_model.flight_controller.fc_parameters["FRAME_CLASS"] = class_num
            frame_types = motor_test_model.get_current_frame_class_types()
            assert len(frame_types) > 0, f"Class {class_num} should have frame types"

    def test_multiple_types_available_for_dotriaconta_class(self, motor_test_model) -> None:
        """
        SCRIPTINGMATRIX frame class offers multiple type configurations.

        GIVEN: Class 15 with multiple type variants (0=PLUS, 1=X, 14=CW_X)
        WHEN: User selects FRAME_CLASS=15
        THEN: All type options are presented
        """
        motor_test_model._motor_data_loader.data = {
            "layouts": [
                {"Class": 15, "ClassName": "SCRIPTINGMATRIX", "Type": 0, "TypeName": "PLUS", "motors": []},
                {"Class": 15, "ClassName": "SCRIPTINGMATRIX", "Type": 1, "TypeName": "DOTRIACONTA/X", "motors": []},
                {"Class": 15, "ClassName": "SCRIPTINGMATRIX", "Type": 14, "TypeName": "CW_X", "motors": []},
            ]
        }
        motor_test_model.flight_controller.fc_parameters["FRAME_CLASS"] = 15

        frame_types = motor_test_model.get_current_frame_class_types()

        assert len(frame_types) == 3
        assert frame_types[0] == "PLUS"
        assert frame_types[1] == "DOTRIACONTA/X"
        assert frame_types[14] == "CW_X"

    def test_frame_options_include_all_defined_classes(self, motor_test_model) -> None:
        """
        Frame options listing includes all defined classes regardless of numbering.

        GIVEN: Motor data with various non-sequential class numbers
        WHEN: User requests all frame options
        THEN: Response includes all class names as keys
        """
        motor_test_model._motor_data_loader.data = {
            "layouts": [
                {"Class": 1, "ClassName": "QUAD", "Type": 0, "TypeName": "PLUS", "motors": []},
                {"Class": 5, "ClassName": "Y6", "Type": 0, "TypeName": "default", "motors": []},
                {"Class": 15, "ClassName": "SCRIPTINGMATRIX", "Type": 1, "TypeName": "DOTRIACONTA/X", "motors": []},
            ]
        }

        frame_options = motor_test_model.get_frame_options()

        assert "QUAD" in frame_options
        assert "Y6" in frame_options
        assert "SCRIPTINGMATRIX" in frame_options
        assert len(frame_options) == 3
