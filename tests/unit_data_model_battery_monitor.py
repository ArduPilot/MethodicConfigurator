#!/usr/bin/env python3

"""
Unit tests for battery monitor data model.

This file tests the BatteryMonitorDataModel class in isolation using mocks.
Tests focus on business logic, status determination, and data retrieval.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from math import isnan, nan
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
from ardupilot_methodic_configurator.data_model_battery_monitor import BatteryMonitorDataModel

# pylint: disable=redefined-outer-name,protected-access


# ==================== FIXTURES ====================


@pytest.fixture
def connected_flight_controller_with_battery_enabled() -> MagicMock:
    """
    Fixture providing a connected flight controller with battery monitoring enabled.

    Simulates realistic battery parameters and telemetry responses.
    """
    fc = MagicMock(spec=FlightController)
    fc.master = MagicMock()  # Simulate connected state
    fc.fc_parameters = {
        "BATT_MONITOR": 4,  # Battery monitoring enabled
        "BATT_ARM_VOLT": 11.0,  # Minimum safe voltage
        "MOT_BAT_VOLT_MAX": 16.8,  # Maximum safe voltage
    }

    fc.is_battery_monitoring_enabled.return_value = True
    fc.get_voltage_thresholds.return_value = (11.0, 16.8)
    fc.get_battery_status.return_value = ((12.4, 2.1), "")  # Voltage, current, message
    fc.request_periodic_battery_status.return_value = None

    return fc


@pytest.fixture
def disconnected_flight_controller() -> MagicMock:
    """Fixture providing a disconnected flight controller."""
    fc = MagicMock(spec=FlightController)
    fc.master = None  # Simulate disconnected state
    fc.fc_parameters = None

    return fc


@pytest.fixture
def connected_flight_controller_battery_disabled() -> MagicMock:
    """Fixture providing a connected flight controller with battery monitoring disabled."""
    fc = MagicMock(spec=FlightController)
    fc.master = MagicMock()  # Simulate connected state
    fc.fc_parameters = {"BATT_MONITOR": 0}  # Battery monitoring disabled

    fc.is_battery_monitoring_enabled.return_value = False
    fc.get_voltage_thresholds.return_value = (nan, nan)

    return fc


@pytest.fixture
def battery_monitor_data_model(
    connected_flight_controller_with_battery_enabled: MagicMock,
) -> BatteryMonitorDataModel:
    """Fixture providing a battery monitor data model with connected flight controller."""
    return BatteryMonitorDataModel(connected_flight_controller_with_battery_enabled)


# ==================== UNIT TESTS ====================


class TestBatteryMonitorWithConnectedFlightController:
    """Test battery monitor behavior when flight controller is connected and battery monitoring enabled."""

    def test_user_sees_voltage_status_as_critical_when_too_high(
        self, connected_flight_controller_with_battery_enabled: MagicMock
    ) -> None:
        """
        User sees "critical" voltage status when battery voltage is too high.

        GIVEN: Battery voltage is 17.0V (above MOT_BAT_VOLT_MAX threshold of 16.8V)
        WHEN: User checks the voltage status
        THEN: Status should be "critical"
        AND: Color should be "red" for immediate visual alert
        """
        # Arrange: Configure high battery voltage
        connected_flight_controller_with_battery_enabled.get_battery_status.return_value = (
            (17.0, 2.1),
            "",
        )
        model = BatteryMonitorDataModel(connected_flight_controller_with_battery_enabled)

        # Act: Check voltage status
        status = model.get_voltage_status()
        color = model.get_battery_status_color()

        # Assert: Status reflects critical condition
        assert status == "critical", "Voltage above maximum threshold should be critical"
        assert color == "red", "Critical status should be red"

    def test_user_sees_battery_stream_established_on_first_read(
        self, battery_monitor_data_model: BatteryMonitorDataModel
    ) -> None:
        """
        Battery status stream is established on first read.

        GIVEN: A user requests battery status for the first time
        WHEN: The flight controller returns valid battery data (message is empty)
        THEN: The stream should be marked as established internally
        AND: Subsequent calls should reuse the cached stream (not re-request)
        """
        # Arrange: Model starts with stream not established
        model = battery_monitor_data_model
        assert model._got_battery_status is False, "Stream should not be established initially"

        # Act: First call retrieves battery status
        status1 = model.get_battery_status()
        first_request_made = model.flight_controller.request_periodic_battery_status.called

        # Second call should not re-request if data is still coming
        model.flight_controller.request_periodic_battery_status.reset_mock()
        status2 = model.get_battery_status()
        second_request_made = model.flight_controller.request_periodic_battery_status.called

        # Assert: Stream established after first data reception
        assert status1 == (12.4, 2.1), "First call should return battery data"
        assert first_request_made, "First call should request periodic stream"
        assert model._got_battery_status is True, "Stream should be marked as established"
        assert status2 == (12.4, 2.1), "Second call should return cached data"
        assert not second_request_made, "Second call should not re-request if data flowing"

    def test_flight_controller_request_periodic_battery_status_called_on_first_read(
        self, battery_monitor_data_model: BatteryMonitorDataModel
    ) -> None:
        """
        Flight controller's periodic battery status request is initiated on first read.

        GIVEN: A fresh battery monitor data model
        WHEN: Battery status is requested for the first time
        THEN: request_periodic_battery_status(500000) should be called on the flight controller
        """
        # Arrange: Fresh model instance
        model = battery_monitor_data_model
        fc = model.flight_controller

        # Act: First battery status request
        model.get_battery_status()

        # Assert: Periodic status request was initiated
        fc.request_periodic_battery_status.assert_called_once_with(500000)


class TestBatteryMonitorWithBatteryMonitoringDisabled:  # pylint: disable=too-few-public-methods
    """Test battery monitor behavior when battery monitoring is disabled on flight controller."""

    def test_battery_monitoring_check_returns_false_when_disabled(
        self, connected_flight_controller_battery_disabled: MagicMock
    ) -> None:
        """
        Battery monitoring check returns False when BATT_MONITOR is 0.

        GIVEN: A flight controller with battery monitoring disabled
        WHEN: is_battery_monitoring_enabled() is called
        THEN: Should return False
        """
        # Arrange: Battery monitoring disabled
        model = BatteryMonitorDataModel(connected_flight_controller_battery_disabled)

        # Act: Check if battery monitoring is enabled
        result = model.is_battery_monitoring_enabled()

        # Assert: Returns False as expected
        assert result is False, "Should return False when BATT_MONITOR == 0"


class TestBatteryMonitorWithDisconnectedFlightController:
    """Test battery monitor behavior when flight controller is disconnected."""

    def test_battery_monitoring_check_returns_false_when_disconnected(self, disconnected_flight_controller: MagicMock) -> None:
        """
        Battery monitoring check returns False when flight controller is disconnected.

        GIVEN: Flight controller is not connected (master is None)
        WHEN: is_battery_monitoring_enabled() is called
        THEN: Should return False
        """
        # Arrange: Disconnected FC
        model = BatteryMonitorDataModel(disconnected_flight_controller)

        # Act: Check battery monitoring status
        result = model.is_battery_monitoring_enabled()

        # Assert: Returns False when disconnected
        assert result is False, "Should return False when flight controller disconnected"

    def test_connection_status_reflects_disconnected_state(self, disconnected_flight_controller: MagicMock) -> None:
        """
        refresh_connection_status() returns False when flight controller is disconnected.

        GIVEN: Flight controller is disconnected
        WHEN: refresh_connection_status() is called
        THEN: Should return False
        """
        # Arrange: Disconnected FC
        model = BatteryMonitorDataModel(disconnected_flight_controller)

        # Act: Check connection status
        connected = model.refresh_connection_status()

        # Assert: Reflects disconnected state
        assert connected is False, "Should return False when disconnected"


class TestBatteryMonitorThresholdHandling:
    """Test battery monitor voltage threshold detection and evaluation."""

    def test_voltage_thresholds_correctly_retrieved_from_flight_controller(
        self, battery_monitor_data_model: BatteryMonitorDataModel
    ) -> None:
        """
        Voltage thresholds are correctly retrieved from flight controller parameters.

        GIVEN: Flight controller has BATT_ARM_VOLT=11.0 and MOT_BAT_VOLT_MAX=16.8
        WHEN: get_voltage_thresholds() is called
        THEN: Should return (11.0, 16.8)
        """
        # Arrange: Model with configured thresholds
        model = battery_monitor_data_model

        # Act: Get voltage thresholds
        min_volt, max_volt = model.get_voltage_thresholds()

        # Assert: Correct thresholds returned
        assert min_volt == 11.0, "Minimum voltage threshold should be BATT_ARM_VOLT"
        assert max_volt == 16.8, "Maximum voltage threshold should be MOT_BAT_VOLT_MAX"

    def test_voltage_boundary_values_critical_at_exact_min_threshold(
        self, connected_flight_controller_with_battery_enabled: MagicMock
    ) -> None:
        """
        Voltage at exact minimum threshold is considered critical.

        GIVEN: Minimum threshold is 11.0V and voltage is exactly 11.0V
        WHEN: Voltage status is checked
        THEN: Status should be "critical" (must be strictly > min)
        """
        # Arrange: Set voltage at exact minimum
        connected_flight_controller_with_battery_enabled.get_battery_status.return_value = (
            (11.0, 2.1),
            "",
        )
        model = BatteryMonitorDataModel(connected_flight_controller_with_battery_enabled)

        # Act: Check voltage status
        status = model.get_voltage_status()

        # Assert: At minimum boundary is critical
        assert status == "critical", "Voltage at minimum threshold should be critical"

    def test_voltage_boundary_values_safe_at_max_threshold(
        self, connected_flight_controller_with_battery_enabled: MagicMock
    ) -> None:
        """
        Voltage just below maximum threshold is considered safe.

        GIVEN: Maximum threshold is 16.8V and voltage is 16.79V
        WHEN: Voltage status is checked
        THEN: Status should be "safe" (must be strictly < max, not <=)
        """
        # Arrange: Set voltage just below maximum
        connected_flight_controller_with_battery_enabled.get_battery_status.return_value = (
            (16.79, 2.1),
            "",
        )
        model = BatteryMonitorDataModel(connected_flight_controller_with_battery_enabled)

        # Act: Check voltage status
        status = model.get_voltage_status()

        # Assert: Just below maximum is safe
        assert status == "safe", "Voltage just below maximum threshold should be safe"

    def test_voltage_boundary_values_critical_at_exact_max_threshold(
        self, connected_flight_controller_with_battery_enabled: MagicMock
    ) -> None:
        """
        Voltage at exact maximum threshold is considered critical.

        GIVEN: Maximum threshold is 16.8V and voltage is exactly 16.8V
        WHEN: Voltage status is checked
        THEN: Status should be "critical" (must be strictly < max)
        """
        # Arrange: Set voltage at exact maximum
        connected_flight_controller_with_battery_enabled.get_battery_status.return_value = (
            (16.8, 2.1),
            "",
        )
        model = BatteryMonitorDataModel(connected_flight_controller_with_battery_enabled)

        # Act: Check voltage status
        status = model.get_voltage_status()

        # Assert: At maximum boundary is critical
        assert status == "critical", "Voltage at maximum threshold should be critical"


class TestBatteryMonitorConnectionStatusIntegration:
    """Test battery monitor connection status checks and integration."""

    def test_connection_status_reflects_connected_state(self, battery_monitor_data_model: BatteryMonitorDataModel) -> None:
        """
        refresh_connection_status() returns True when flight controller is connected.

        GIVEN: Flight controller is connected (master is not None)
        WHEN: refresh_connection_status() is called
        THEN: Should return True
        """
        # Arrange: Connected FC
        model = battery_monitor_data_model

        # Act: Check connection status
        connected = model.refresh_connection_status()

        # Assert: Reflects connected state
        assert connected is True, "Should return True when flight controller connected"

    def test_battery_status_not_requested_when_disconnected(self, disconnected_flight_controller: MagicMock) -> None:
        """
        Battery status is not requested from flight controller when disconnected.

        GIVEN: Flight controller is disconnected
        WHEN: get_battery_status() is called
        THEN: Should return None without calling request_periodic_battery_status()
        """
        # Arrange: Disconnected FC
        model = BatteryMonitorDataModel(disconnected_flight_controller)

        # Act: Try to get battery status
        status = model.get_battery_status()

        # Assert: No request made when disconnected
        assert status is None, "Should return None when disconnected"
        assert not disconnected_flight_controller.request_periodic_battery_status.called, (
            "Should not request periodic status when disconnected"
        )

    def test_voltage_thresholds_unavailable_when_disconnected(self, disconnected_flight_controller: MagicMock) -> None:
        """
        Voltage thresholds return NaN when flight controller is disconnected.

        GIVEN: Flight controller is disconnected
        WHEN: get_voltage_thresholds() is called
        THEN: Should return (NaN, NaN)
        """
        # Arrange: Disconnected FC
        model = BatteryMonitorDataModel(disconnected_flight_controller)

        # Act: Get voltage thresholds
        min_volt, max_volt = model.get_voltage_thresholds()

        # Assert: Both thresholds are NaN
        assert isnan(min_volt), "Minimum threshold should be NaN when disconnected"
        assert isnan(max_volt), "Maximum threshold should be NaN when disconnected"


class TestBatteryMonitorDataModelEdgeCases:
    """Test edge cases and error handling in battery monitor data model."""

    def test_battery_monitoring_disabled_returns_none(self, connected_flight_controller_battery_disabled: MagicMock) -> None:
        """
        Getting battery status when disabled returns None.

        GIVEN: Battery monitoring is disabled (BATT_MONITOR = 0)
        WHEN: get_battery_status() is called
        THEN: Should return None
        """
        # Arrange: Disable battery monitoring
        model = BatteryMonitorDataModel(connected_flight_controller_battery_disabled)

        # Act: Try to get battery status
        status = model.get_battery_status()

        # Assert: Returns None
        assert status is None

    def test_battery_status_error_message_returns_none(
        self, connected_flight_controller_with_battery_enabled: MagicMock
    ) -> None:
        """
        Error message from get_battery_status returns None.

        GIVEN: Flight controller returns error message with battery status
        WHEN: get_battery_status() is called
        THEN: Should return None
        """
        # Arrange: Return error message
        connected_flight_controller_with_battery_enabled.get_battery_status.return_value = (
            None,
            "Failed to read battery sensor",
        )
        model = BatteryMonitorDataModel(connected_flight_controller_with_battery_enabled)

        # Act: Get battery status
        status = model.get_battery_status()

        # Assert: Returns None
        assert status is None

    def test_nan_voltage_thresholds_return_unavailable_status(
        self, connected_flight_controller_with_battery_enabled: MagicMock
    ) -> None:
        """
        NaN voltage thresholds result in unavailable status.

        GIVEN: Flight controller returns NaN for voltage thresholds
        WHEN: get_voltage_status() is called
        THEN: Should return "unavailable" status
        """
        # Arrange: Return NaN thresholds
        connected_flight_controller_with_battery_enabled.get_voltage_thresholds.return_value = (nan, nan)
        connected_flight_controller_with_battery_enabled.get_battery_status.return_value = ((12.4, 2.1), "")
        model = BatteryMonitorDataModel(connected_flight_controller_with_battery_enabled)

        # Act: Check voltage status
        status = model.get_voltage_status()

        # Assert: Returns unavailable
        assert status == "unavailable"
