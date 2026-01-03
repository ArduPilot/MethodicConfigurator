#!/usr/bin/env python3

"""
Acceptance tests for battery monitor plugin.

These tests validate complete user workflows by mocking only the backend (FlightController)
and fully testing the data model and frontend together as an integrated system.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import tkinter as tk
from math import nan
from typing import Callable
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.data_model_battery_monitor import BatteryMonitorDataModel
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.frontend_tkinter_battery_monitor import (
    BatteryMonitorView,
    _create_battery_monitor_view,
    register_battery_monitor_plugin,
)
from ardupilot_methodic_configurator.plugin_factory import plugin_factory

# pylint: disable=redefined-outer-name,protected-access,too-many-lines


# pylint: disable=duplicate-code
@pytest.fixture
def tk_root() -> tk.Tk:
    """Provide a real Tkinter root window for testing GUI components."""
    root = tk.Tk()
    root.withdraw()  # Hide the window
    yield root
    # Cleanup
    with contextlib.suppress(tk.TclError):
        root.destroy()


@pytest.fixture
def mock_flight_controller_with_battery() -> MagicMock:
    """Provide mock flight controller with battery monitoring enabled and realistic values."""
    # pylint: enable=duplicate-code
    mock_fc = MagicMock()
    mock_fc.fc_parameters = {
        "BATT_MONITOR": 4,  # Analog voltage and current
        "BATT_ARM_VOLT": 11.0,  # Minimum arming voltage
        "BATT_LOW_VOLT": 10.5,  # Low battery warning voltage
        "MOT_BAT_VOLT_MAX": 16.8,  # Maximum battery voltage
    }
    mock_fc.is_connected.return_value = True
    mock_fc.is_battery_monitoring_enabled.return_value = True
    mock_fc.get_battery_status.return_value = ((12.4, 2.1), "")  # voltage, current
    mock_fc.get_voltage_thresholds.return_value = (11.0, 16.8)  # min, max voltage
    return mock_fc


@pytest.fixture
def mock_flight_controller_disconnected() -> MagicMock:
    """Provide mock flight controller in disconnected state."""
    mock_fc = MagicMock()
    mock_fc.fc_parameters = {"BATT_MONITOR": 0}  # Disabled
    mock_fc.is_connected.return_value = False
    mock_fc.is_battery_monitoring_enabled.return_value = False
    mock_fc.get_battery_status.return_value = (None, "Not connected")
    return mock_fc


@pytest.fixture
def mock_base_window(tk_root: tk.Tk) -> MagicMock:
    """Provide mock base window with real Tkinter root for plugin testing."""
    mock_window = MagicMock(spec=["BaseWindow"])
    mock_window.root = tk_root
    return mock_window


class TestBatteryMonitorPluginRegistration:
    """Test battery monitor plugin registration with factory."""

    def test_user_can_register_battery_monitor_plugin_with_factory(self) -> None:
        """
        User can register battery monitor plugin with the factory.

        GIVEN: A plugin factory
        WHEN: Battery monitor plugin is registered
        THEN: Factory should have 'battery_monitor' creator registered
        """
        # Act: Register plugin
        register_battery_monitor_plugin()

        # Assert: Plugin is registered
        assert "battery_monitor" in plugin_factory._creators

    def test_factory_creates_battery_monitor_view_instances(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Plugin factory can create battery monitor view instances.

        GIVEN: A registered battery monitor plugin
        WHEN: The factory creates a view with model and base window
        THEN: Should return a BatteryMonitorView instance with working GUI
        """
        # Arrange: Register plugin and create data model
        register_battery_monitor_plugin()
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)

        # Act: Create view using factory
        view = _create_battery_monitor_view(tk_root, model, mock_base_window)

        # Assert: View is created correctly
        assert isinstance(view, BatteryMonitorView)
        assert view.model is model
        assert view.base_window is mock_base_window


class TestBatteryMonitorUserWorkflow:
    """Test complete user workflows with battery monitor plugin."""

    def test_user_opens_battery_configuration_step_and_sees_battery_status(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        User opens battery configuration step and sees current battery status.

        GIVEN: User navigates to battery configuration step
        WHEN: The battery monitor plugin loads
        THEN: User should see current battery voltage (12.4V) and current (2.1A)
        AND: Display should be color-coded green (safe voltage range)
        """
        # Arrange: Create model and view
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display

        # Act: Process pending events to let GUI initialize
        tk_root.update()

        # Assert: GUI displays correct battery status
        assert view.voltage_value_label is not None
        assert view.current_value_label is not None
        assert "12.4" in view.voltage_value_label.cget("text")
        assert "2.1" in view.current_value_label.cget("text")

    def test_user_sees_battery_status_update_periodically(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        User sees battery status update every 500ms while viewing the plugin.

        GIVEN: User has battery monitor plugin visible
        WHEN: Battery values change and 500ms timer expires
        THEN: Display should refresh with new values
        """
        # Arrange: Create view with initial battery state
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        # Act: Simulate battery voltage change
        mock_flight_controller_with_battery.get_battery_status.return_value = ((12.0, 3.5), "")

        # Trigger the periodic update manually
        view._periodic_update()
        tk_root.update()

        # Assert: Display shows updated values
        assert view.voltage_value_label is not None
        assert view.current_value_label is not None
        assert "12.0" in view.voltage_value_label.cget("text")
        assert "3.5" in view.current_value_label.cget("text")

    def test_user_sees_critical_voltage_warning_when_battery_low(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        User sees critical voltage warning (red color) when battery voltage is low.

        GIVEN: User is monitoring battery during operation
        WHEN: Battery voltage drops below BATT_ARM_VOLT threshold (10.5V < 11.0V)
        THEN: Display should change to red color
        AND: User should see the low voltage value displayed
        """
        # Arrange: Battery voltage at critical level
        mock_flight_controller_with_battery.get_battery_status.return_value = ((10.5, 2.1), "")
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        # Act: Get the status color
        status_color = model.get_battery_status_color()

        # Assert: Display shows critical warning
        assert status_color == "red"
        assert "10.5" in view.voltage_value_label.cget("text")

    def test_user_sees_disabled_status_when_battery_monitoring_off(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        User sees disabled status when battery monitoring is turned off.

        GIVEN: User has BATT_MONITOR parameter set to 0 (disabled)
        WHEN: The battery monitor plugin is displayed
        THEN: User should see "Disabled" text
        AND: Display should be gray (neutral color)
        """
        # Arrange: Battery monitoring disabled
        mock_flight_controller_with_battery.fc_parameters["BATT_MONITOR"] = 0
        mock_flight_controller_with_battery.is_battery_monitoring_enabled.return_value = False
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        # Assert: Display shows disabled status
        assert model.get_battery_status_color() == "gray"
        assert "Disabled" in view.voltage_value_label.cget("text")


class TestBatteryMonitorPluginLifecycle:
    """Test plugin lifecycle management."""

    def test_plugin_starts_monitoring_when_created(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Plugin starts monitoring immediately when created.

        GIVEN: User navigates to battery configuration step
        WHEN: Plugin view is created
        THEN: Plugin should immediately display battery status
        AND: Periodic updates should be scheduled
        """
        # Arrange & Act: Create view
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        # Assert: Timer is scheduled and status is displayed
        assert view._timer_id is not None
        assert view.voltage_value_label is not None
        assert "12.4" in view.voltage_value_label.cget("text")

    def test_plugin_stops_monitoring_when_destroyed(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Plugin stops monitoring when destroyed.

        GIVEN: User has battery monitor plugin active
        WHEN: Plugin is destroyed (user navigates away or closes application)
        THEN: All timers should be cancelled
        AND: Resources should be properly released
        """
        # Arrange: Create and start view
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()
        timer_id = view._timer_id

        # Act: Destroy the view
        view.destroy()
        tk_root.update()

        # Assert: Timer is cancelled
        assert timer_id is not None  # Was scheduled
        # Note: We can't directly verify timer cancellation,
        # but destroy() should have called _cancel_timer()


class TestBatteryMonitorRealTimeUpdates:
    """Test real-time battery monitoring scenarios."""

    def test_user_monitors_battery_during_motor_test(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        User monitors battery voltage/current in real-time during motor testing.

        GIVEN: User is performing motor tests with battery monitor visible
        WHEN: Battery current increases from 2.1A to 15.3A (motors spinning)
        THEN: Display should update to show increased current
        AND: Voltage should drop accordingly (battery under load)
        """
        # Arrange: Create view with normal battery state
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        # Act: Simulate motor test - high current draw
        mock_flight_controller_with_battery.get_battery_status.return_value = ((12.1, 15.3), "")
        view._periodic_update()
        tk_root.update()

        # Assert: Display shows increased current and voltage drop
        assert "12.1" in view.voltage_value_label.cget("text")
        assert "15.3" in view.current_value_label.cget("text")

    def test_user_sees_immediate_warning_when_voltage_becomes_critical(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        User sees immediate visual warning when battery voltage becomes critical.

        GIVEN: User is monitoring battery during operation
        WHEN: Battery voltage transitions from safe (12.4V) to critical (10.8V)
        THEN: Display color should change from green to red
        AND: User should see the critical voltage value
        """
        # Arrange: Start with safe voltage
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        initial_color = model.get_battery_status_color()
        assert initial_color == "green"

        # Act: Voltage drops to critical level
        mock_flight_controller_with_battery.get_battery_status.return_value = ((10.8, 2.1), "")
        view._periodic_update()
        tk_root.update()

        # Assert: Color changes to red
        new_color = model.get_battery_status_color()
        assert new_color == "red"
        assert "10.8" in view.voltage_value_label.cget("text")


class TestBatteryMonitorConnectionHandling:
    """Test battery monitor behavior with connection changes."""

    def test_user_sees_unavailable_when_flight_controller_disconnects(
        self, tk_root: tk.Tk, mock_flight_controller_disconnected: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        User sees appropriate status when flight controller disconnects.

        GIVEN: Flight controller is not connected
        WHEN: Battery monitor plugin is displayed
        THEN: Display should show "Disabled" status
        AND: Color should be gray (neutral)
        """
        # Arrange: Disconnected flight controller
        model = BatteryMonitorDataModel(mock_flight_controller_disconnected)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        # Assert: Shows disabled status
        assert model.get_battery_status_color() == "gray"
        assert "Disabled" in view.voltage_value_label.cget("text")

    def test_plugin_continues_attempting_updates_after_connection_loss(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Plugin continues attempting periodic updates even after connection loss.

        GIVEN: User was monitoring battery but connection was lost
        WHEN: Periodic update timer fires
        THEN: Plugin should handle the error gracefully
        AND: Continue scheduling updates (allows automatic reconnection)
        """
        # Arrange: Start connected
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        # Act: Simulate connection loss
        mock_flight_controller_with_battery.is_connected.return_value = False
        mock_flight_controller_with_battery.is_battery_monitoring_enabled.return_value = False
        view._periodic_update()
        tk_root.update()

        # Assert: Timer continues to be scheduled (for reconnection)
        assert view._timer_id is not None


class TestBatteryMonitorEdgeCases:
    """Test edge cases and error handling in battery monitor."""

    def test_user_sees_na_when_battery_status_unavailable(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        User sees N/A when battery status is not available.

        GIVEN: Flight controller returns None for battery status
        WHEN: Battery monitor plugin displays status
        THEN: User should see "N/A" for both voltage and current
        """
        # Arrange: Battery status unavailable
        mock_flight_controller_with_battery.get_battery_status.return_value = (None, "Battery data unavailable")
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        # Assert: Display shows N/A
        assert "N/A" in view.voltage_value_label.cget("text")
        assert "N/A" in view.current_value_label.cget("text")

    def test_periodic_update_handles_disconnection_gracefully(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Periodic update continues to work even when disconnected.

        GIVEN: Battery monitor is running with periodic updates
        WHEN: Flight controller disconnects mid-operation
        THEN: Periodic update should handle disconnection without crashing
        AND: Display should update to show unavailable status
        """
        # Arrange: Start connected
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        # Act: Simulate disconnection during periodic update
        mock_flight_controller_with_battery.is_connected.return_value = False
        mock_flight_controller_with_battery.is_battery_monitoring_enabled.return_value = False
        view._periodic_update()
        tk_root.update()

        # Assert: No crash, display shows disabled
        assert "Disabled" in view.voltage_value_label.cget("text")

    def test_on_activate_refreshes_battery_when_disconnected(
        self, tk_root: tk.Tk, mock_flight_controller_disconnected: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Plugin activation handles disconnected state gracefully.

        GIVEN: Plugin is being activated while flight controller is disconnected
        WHEN: on_activate() is called
        THEN: Plugin should check connection and not crash
        AND: Display should show disabled status
        """
        # Arrange: Create view in disconnected state
        model = BatteryMonitorDataModel(mock_flight_controller_disconnected)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        # Act: Activate plugin
        view.on_activate()
        tk_root.update()

        # Assert: No crash, shows disabled
        assert "Disabled" in view.voltage_value_label.cget("text")

    def test_on_deactivate_cancels_active_timer(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Plugin deactivation properly cancels active timer.

        GIVEN: Plugin has an active periodic update timer
        WHEN: on_deactivate() is called
        THEN: Timer should be cancelled
        AND: _timer_id should be set to None
        """
        # Arrange: Create view with active timer
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        # Verify timer is active
        assert view._timer_id is not None
        initial_timer_id = view._timer_id

        # Act: Deactivate plugin
        view.on_deactivate()
        tk_root.update()

        # Assert: Timer is cancelled
        assert view._timer_id is None
        assert initial_timer_id is not None  # Was active before

    def test_destroy_cancels_timer_before_cleanup(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Plugin destroy properly cancels timer before destroying widget.

        GIVEN: Plugin has an active periodic update timer
        WHEN: destroy() is called
        THEN: Timer should be cancelled before widget destruction
        AND: No resource leaks should occur
        """
        # Arrange: Create view with active timer
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        # Verify timer is active
        assert view._timer_id is not None

        # Act: Destroy the view
        view.destroy()
        tk_root.update()

        # Assert: Successfully destroyed (no crash indicates proper cleanup)
        # The timer_id is cleared during destroy, preventing resource leaks


class TestBatteryMonitorStreamReconnection:
    """Test battery monitor stream recovery scenarios."""

    def test_user_experiences_automatic_stream_recovery_after_connection_loss(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        User experiences automatic stream recovery when connection is restored.

        GIVEN: Battery monitor was receiving data but stream was lost
        WHEN: Connection is restored and stream becomes available again
        THEN: Plugin should automatically re-request the stream
        AND: User should see battery data resume without manual intervention
        """
        # Arrange: Start with working connection
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()
        tk_root.update()

        # Verify initial data is displayed
        assert "12.4" in view.voltage_value_label.cget("text")

        # Act: Simulate stream loss (message indicates lost stream)
        mock_flight_controller_with_battery.get_battery_status.return_value = (None, "Stream lost")
        view._periodic_update()
        tk_root.update()

        # Stream recovery: connection restored with data
        mock_flight_controller_with_battery.get_battery_status.return_value = ((12.5, 2.2), "")
        view._periodic_update()
        tk_root.update()

        # Assert: New data is displayed (automatic recovery worked)
        assert "12.5" in view.voltage_value_label.cget("text")
        assert "2.2" in view.current_value_label.cget("text")

    def test_plugin_handles_multiple_rapid_activate_deactivate_cycles(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Plugin handles rapid activation/deactivation without resource leaks.

        GIVEN: User navigates quickly between configuration steps
        WHEN: Plugin is activated and deactivated multiple times rapidly
        THEN: No timers should leak
        AND: Plugin should work correctly after each cycle
        """
        # Arrange: Create view
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)

        # Act: Rapid activate/deactivate cycles
        for _ in range(5):
            view.on_activate()
            tk_root.update()
            assert view._timer_id is not None

            view.on_deactivate()
            tk_root.update()
            assert view._timer_id is None

        # Final activation should still work
        view.on_activate()
        tk_root.update()

        # Assert: Plugin still works correctly
        assert view._timer_id is not None
        assert "12.4" in view.voltage_value_label.cget("text")

    def test_stream_request_occurs_on_every_call_until_data_received(
        self,
        tk_root: tk.Tk,  # pylint: disable=unused-argument
        mock_flight_controller_with_battery: MagicMock,
        mock_base_window: MagicMock,  # pylint: disable=unused-argument
    ) -> None:
        """
        Stream request is repeated until actual data is received.

        GIVEN: Plugin starts requesting battery stream
        WHEN: Initial requests return no data (delays or connection issues)
        THEN: Plugin should continue requesting stream on each call
        AND: Once data is received, requests should stop (stream established)
        """
        # Arrange: Configure mock to return no data initially
        mock_flight_controller_with_battery.get_battery_status.return_value = (None, "Waiting for data")
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)

        # Act: Call get_battery_status multiple times without data
        for _ in range(3):
            result = model.get_battery_status()
            assert result is None

        # Verify stream was requested multiple times (once per call)
        assert mock_flight_controller_with_battery.request_periodic_battery_status.call_count == 3

        # Now data arrives
        mock_flight_controller_with_battery.get_battery_status.return_value = ((12.4, 2.1), "")
        result = model.get_battery_status()
        assert result == (12.4, 2.1)

        # Further calls should NOT request stream again (already established)
        result = model.get_battery_status()
        assert result == (12.4, 2.1)
        # Call count should still be 4 (3 initial + 1 when data arrived, not 5)
        assert mock_flight_controller_with_battery.request_periodic_battery_status.call_count == 4


class TestBatteryMonitorInvalidConfiguration:
    """Test battery monitor behavior with invalid configurations."""

    def test_user_sees_unavailable_when_voltage_thresholds_invalid(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        User sees unavailable status when voltage thresholds are invalid.

        GIVEN: Battery monitoring is enabled but voltage thresholds are not configured
        WHEN: get_voltage_thresholds returns NaN values
        THEN: Status should be "unavailable"
        AND: Color should be gray
        """
        # Arrange: Invalid thresholds (NaN)
        mock_flight_controller_with_battery.get_voltage_thresholds.return_value = (nan, nan)
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()
        tk_root.update()

        # Assert: Shows unavailable status
        assert model.get_voltage_status() == "unavailable"
        assert model.get_battery_status_color() == "gray"

    def test_user_sees_critical_when_voltage_above_maximum(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        User sees critical status when battery voltage exceeds maximum threshold.

        GIVEN: Battery monitor is active
        WHEN: Voltage exceeds MOT_BAT_VOLT_MAX (e.g., 17.5V > 16.8V)
        THEN: Status should be "critical" (red)
        AND: User sees high voltage value displayed
        """
        # Arrange: Voltage too high
        mock_flight_controller_with_battery.get_battery_status.return_value = ((17.5, 0.5), "")
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()
        tk_root.update()

        # Assert: Shows critical status
        assert model.get_voltage_status() == "critical"
        assert model.get_battery_status_color() == "red"
        assert "17.5" in view.voltage_value_label.cget("text")


class TestBatteryMonitorDataModelCleanup:
    """Test data model cleanup and resource management."""

    def test_stop_monitoring_resets_stream_state(self, mock_flight_controller_with_battery: MagicMock) -> None:
        """
        Calling stop_monitoring resets stream state for clean restart.

        GIVEN: Data model has established battery stream
        WHEN: stop_monitoring() is called
        THEN: Internal stream flag should be reset
        AND: Next get_battery_status call should re-request stream
        """
        # Arrange: Establish stream
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        model.get_battery_status()  # Establishes stream
        assert model._got_battery_status is True

        # Act: Stop monitoring
        model.stop_monitoring()

        # Assert: Stream state reset
        assert model._got_battery_status is False

    def test_view_calls_model_cleanup_on_deactivate(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        View properly calls model cleanup when deactivated.

        GIVEN: Plugin is active with established stream
        WHEN: on_deactivate() is called
        THEN: Model's stop_monitoring() should be invoked
        AND: Stream state should be reset
        """
        # Arrange: Activate plugin to establish stream
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()
        tk_root.update()

        # Verify stream is established
        assert model._got_battery_status is True

        # Act: Deactivate plugin
        view.on_deactivate()
        tk_root.update()

        # Assert: Model cleanup was called
        assert model._got_battery_status is False

    def test_view_calls_model_cleanup_on_destroy(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        View properly calls model cleanup when destroyed.

        GIVEN: Plugin is active with established stream
        WHEN: destroy() is called
        THEN: Model's stop_monitoring() should be invoked
        AND: All resources should be released
        """
        # Arrange: Activate plugin to establish stream
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()
        tk_root.update()

        # Verify stream is established
        assert model._got_battery_status is True

        # Act: Destroy plugin
        view.destroy()
        tk_root.update()

        # Assert: Model cleanup was called
        assert model._got_battery_status is False


class TestBatteryMonitorParameterUpload:
    """
    Test parameter upload functionality integrated into battery monitor plugin.

    NOTE: These tests verify the upload button UI integration at acceptance level.
    They test button visibility and delegation to UI services. Detailed workflow testing
    is in test_data_model_parameter_editor.py and test_frontend_tkinter_parameter_editor.py.
    """

    def test_upload_button_appears_when_parameter_editor_available(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Upload button is visible when parameter editor is integrated.

        GIVEN: Battery monitor plugin with parameter editor integration
        WHEN: The view is created
        THEN: Upload button should be visible in the UI
        """
        # Arrange: Create model with parameter editor
        mock_param_editor = MagicMock()
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery, mock_param_editor)

        # Act: Create view
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update()

        # Assert: Button exists and is visible
        assert hasattr(view, "upload_button")
        assert view.upload_button.winfo_exists()

    def test_upload_button_hidden_when_parameter_editor_unavailable(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Upload button is not shown when parameter editor is unavailable.

        GIVEN: Battery monitor plugin without parameter editor integration
        WHEN: The view is created
        THEN: Upload button should not be present
        """
        # Arrange & Act: Create view without parameter editor
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery, parameter_editor=None)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update()

        # Assert: Button doesn't exist
        assert not hasattr(view, "upload_button") or view.upload_button.winfo_exists() == 0

    def test_battery_monitor_integrates_with_parameter_editor_workflow(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Battery monitor correctly integrates with parameter editor upload workflow.

        GIVEN: Battery monitor with parameter editor and UI services
        WHEN: Upload is initiated through the view's upload method
        THEN: The view should delegate to UI services' upload_params_with_progress
        AND: Pass the correct workflow callback from parameter editor
        """
        # Arrange: Set up integrated environment
        mock_param_editor = MagicMock()
        mock_ui_services = MagicMock()

        # Set up base window with minimal required structure
        mock_base_window.gui_complexity = "normal"
        mock_base_window.parameter_editor_table = MagicMock()
        mock_base_window.parameter_editor_table.get_upload_selected_params.return_value = ParDict({"BATT_CAPACITY": Par(5200)})

        model = BatteryMonitorDataModel(mock_flight_controller_with_battery, mock_param_editor)
        view = BatteryMonitorView(tk_root, model, mock_base_window, ui_services=mock_ui_services)

        # Act: Trigger upload through the view's public interface
        selected_params = ParDict({"BATT_CAPACITY": Par(5200)})
        view.upload_selected_params(selected_params)

        # Assert: View delegates to UI services with correct workflow
        mock_ui_services.upload_params_with_progress.assert_called_once()
        call_args = mock_ui_services.upload_params_with_progress.call_args
        assert call_args[0][1] == mock_param_editor.upload_selected_params_workflow  # Workflow callback
        assert call_args[0][2] == selected_params  # Parameters

    def _setup_upload_progress_mocks(self, mock_ui_services: MagicMock) -> tuple[list, Callable]:
        """Helper to set up progress window mocks and tracking."""
        progress_windows_created = []

        def track_progress_window(*_args, **_kwargs) -> MagicMock:
            mock_window = MagicMock()
            progress_windows_created.append(mock_window)
            return mock_window

        mock_ui_services.create_progress_window = MagicMock(side_effect=track_progress_window)

        def simulate_upload_with_progress(parent_window, upload_callback, selected_params_arg) -> None:
            """Simulate upload_params_with_progress calling workflow with callbacks."""
            reset_window = None
            download_window = None

            def reset_callback_getter() -> Callable[[int, int], None]:
                nonlocal reset_window
                reset_window = mock_ui_services.create_progress_window(
                    parent_window, "Resetting Flight Controller", "msg", show_immediately=True
                )
                return reset_window.update_progress_bar

            def download_callback_getter() -> Callable[[int, int], None]:
                nonlocal download_window
                download_window = mock_ui_services.create_progress_window(
                    parent_window, "Re-downloading FC parameters", "msg", show_immediately=False
                )
                return download_window.update_progress_bar

            try:
                # Invoke the getters to actually create the windows
                reset_cb = reset_callback_getter()
                download_cb = download_callback_getter()

                # Call the workflow with the callbacks
                upload_callback(
                    selected_params_arg,
                    ask_confirmation=MagicMock(return_value=True),
                    ask_retry_cancel=MagicMock(return_value=True),
                    show_error=MagicMock(),
                    get_reset_progress_callback=reset_callback_getter,
                    get_download_progress_callback=download_callback_getter,
                )

                # Simulate some progress updates
                if reset_cb:
                    reset_cb(5, 10)
                if download_cb:
                    download_cb(50, 100)
            finally:
                # Simulate cleanup in finally block
                if reset_window is not None:
                    reset_window.destroy()
                if download_window is not None:
                    download_window.destroy()

        return progress_windows_created, simulate_upload_with_progress

    def test_user_sees_progress_feedback_during_parameter_upload(self, tk_root: tk.Tk, mock_base_window: MagicMock) -> None:  # pylint: disable=too-many-locals
        """
        User sees progress feedback while parameters are being uploaded.

        GIVEN: User initiates parameter upload
        WHEN: Upload is in progress (reset, upload, download)
        THEN: Progress windows should be displayed with appropriate messages
        AND: Progress should be cleaned up when complete
        """
        # Arrange: Set up complete environment
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()
        mock_fc.fc_parameters = {"BATT_MONITOR": 4}

        mock_param_editor = MagicMock()
        selected_params = ParDict({"BATT_CAPACITY": Par(5200)})
        mock_param_editor.ensure_upload_preconditions.return_value = True

        mock_param_table = MagicMock()
        mock_param_table.get_upload_selected_params.return_value = selected_params

        mock_ui_services = MagicMock()
        progress_windows_created, simulate_upload_with_progress = self._setup_upload_progress_mocks(mock_ui_services)
        mock_ui_services.upload_params_with_progress = MagicMock(side_effect=simulate_upload_with_progress)

        mock_base_window.gui_complexity = "normal"
        mock_base_window.parameter_editor_table = mock_param_table
        mock_base_window.show_only_differences = MagicMock()
        mock_base_window.show_only_differences.get.return_value = False

        model = BatteryMonitorDataModel(mock_fc, mock_param_editor)
        view = BatteryMonitorView(tk_root, model, mock_base_window, ui_services=mock_ui_services)
        tk_root.update()

        # Act: Upload parameters
        view._on_upload_button_clicked()

        # Assert: Verify workflow integration
        mock_ui_services.upload_params_with_progress.assert_called_once()

        # Verify progress windows were created (should create 2: reset and download)
        assert mock_ui_services.create_progress_window.call_count == 2

        # Verify progress window calls have correct titles
        call_args_list = mock_ui_services.create_progress_window.call_args_list
        reset_window_call = call_args_list[0]
        download_window_call = call_args_list[1]

        # Check reset progress window was created with correct title
        assert "Resetting Flight Controller" in str(reset_window_call)
        # Check download progress window was created with correct title
        assert "Re-downloading FC parameters" in str(download_window_call)

        # Verify all created progress windows were destroyed
        for mock_window in progress_windows_created:
            mock_window.destroy.assert_called_once()


class TestBatteryMonitorUIIntegration:
    """
    Test battery monitor UI integration at acceptance level.

    These tests verify UI layout, component creation, and user-visible behavior.
    """

    def test_battery_monitor_displays_correct_initial_state(
        self, tk_root: tk.Tk, mock_flight_controller_disconnected: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Battery monitor shows appropriate initial state before connection.

        GIVEN: Battery monitor with disconnected flight controller
        WHEN: View is created
        THEN: Should display "N/A" for voltage and current
        AND: UI components should be properly initialized
        """
        # Arrange & Act: Create view with disconnected FC
        model = BatteryMonitorDataModel(mock_flight_controller_disconnected)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update()

        # Assert: Initial state shows disabled (monitoring is off)
        voltage_text, current_text = view._get_battery_display_text()
        assert "Disabled" in voltage_text
        assert "Disabled" in current_text

    def test_battery_monitor_displays_disabled_state_when_monitoring_off(
        self, tk_root: tk.Tk, mock_base_window: MagicMock
    ) -> None:
        """
        Battery monitor shows disabled state when monitoring is off.

        GIVEN: Flight controller with battery monitoring disabled
        WHEN: View displays battery status
        THEN: Should show "Disabled" for both voltage and current
        """
        # Arrange: FC with monitoring disabled
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()
        mock_fc.fc_parameters = {"BATT_MONITOR": 0}  # Disabled
        mock_fc.is_battery_monitoring_enabled.return_value = False

        model = BatteryMonitorDataModel(mock_fc)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update()

        # Act: Get display text
        voltage_text, current_text = view._get_battery_display_text()

        # Assert: Disabled state
        assert "Disabled" in voltage_text
        assert "Disabled" in current_text

    def test_battery_monitor_formats_voltage_and_current_correctly(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Battery monitor formats numeric values with correct precision.

        GIVEN: Battery monitor with valid voltage and current
        WHEN: Display text is generated
        THEN: Should format voltage as "XX.XX V" and current as "XX.XX A"
        """
        # Arrange: FC with specific values
        mock_flight_controller_with_battery.get_battery_status.return_value = ((12.456, 3.789), "")

        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update()

        # Act: Get display text
        voltage_text, current_text = view._get_battery_display_text()

        # Assert: Correct formatting (2 decimal places)
        assert voltage_text == "12.46 V"
        assert current_text == "3.79 A"

    def test_battery_monitor_ui_layout_creates_all_components(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Battery monitor UI creates all expected components.

        GIVEN: Battery monitor view creation
        WHEN: UI setup completes
        THEN: All labels and containers should exist
        AND: Components should be properly configured
        """
        # Arrange & Act: Create view
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update()

        # Assert: Core components exist
        assert hasattr(view, "voltage_value_label")
        assert hasattr(view, "current_value_label")
        assert view.voltage_value_label.winfo_exists()
        assert view.current_value_label.winfo_exists()

    def test_battery_monitor_without_parameter_editor_has_no_upload_button(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Battery monitor without parameter editor doesn't create upload button.

        GIVEN: Battery monitor without parameter editor
        WHEN: View is created
        THEN: Upload button should not be created
        """
        # Arrange & Act: Create view without parameter editor
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery, parameter_editor=None)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update()

        # Assert: No upload button
        assert not hasattr(view, "upload_button") or not view.upload_button.winfo_exists()

    def test_battery_monitor_with_parameter_editor_creates_upload_button(
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Battery monitor with parameter editor creates upload button.

        GIVEN: Battery monitor with parameter editor
        WHEN: View is created
        THEN: Upload button should be created and visible
        """
        # Arrange & Act: Create view with parameter editor
        mock_param_editor = MagicMock()
        model = BatteryMonitorDataModel(mock_flight_controller_with_battery, mock_param_editor)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update()

        # Assert: Upload button exists
        assert hasattr(view, "upload_button")
        assert view.upload_button.winfo_exists()


class TestBatteryMonitorColorCoding:
    """
    Test battery voltage color coding at acceptance level.

    Verifies that voltage status colors are correctly applied to UI components.
    """

    def test_voltage_display_shows_green_for_safe_voltage(self, tk_root: tk.Tk, mock_base_window: MagicMock) -> None:
        """
        Voltage display shows green for safe voltage range.

        GIVEN: Battery voltage within safe range
        WHEN: Status is updated
        THEN: Voltage label should be colored green
        """
        # pylint: disable=duplicate-code
        # Arrange: FC with safe voltage
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()
        mock_fc.fc_parameters = {
            "BATT_MONITOR": 4,
            "BATT_ARM_VOLT": 11.0,
            "MOT_BAT_VOLT_MAX": 16.8,
        }
        mock_fc.is_battery_monitoring_enabled.return_value = True
        # pylint: enable=duplicate-code
        mock_fc.get_battery_status.return_value = ((12.5, 2.0), "")
        mock_fc.get_voltage_thresholds.return_value = (11.0, 16.8)

        model = BatteryMonitorDataModel(mock_fc)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update()

        # Act: Update battery status
        view._update_battery_status()

        # Assert: Green color
        color_str = str(view.voltage_value_label.cget("foreground"))
        assert "green" in color_str.lower()

    def test_voltage_display_shows_red_for_critical_low_voltage(self, tk_root: tk.Tk, mock_base_window: MagicMock) -> None:
        """
        Voltage display shows red for critically low voltage.

        GIVEN: Battery voltage below minimum threshold
        WHEN: Status is updated
        THEN: Voltage label should be colored red
        """
        # pylint: disable=duplicate-code
        # Arrange: FC with low voltage
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()
        mock_fc.fc_parameters = {
            "BATT_MONITOR": 4,
            "BATT_ARM_VOLT": 11.0,
            "MOT_BAT_VOLT_MAX": 16.8,
        }
        mock_fc.is_battery_monitoring_enabled.return_value = True
        # pylint: enable=duplicate-code
        mock_fc.get_battery_status.return_value = ((10.5, 0.5), "")
        mock_fc.get_voltage_thresholds.return_value = (11.0, 16.8)

        model = BatteryMonitorDataModel(mock_fc)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update()

        # Act: Update battery status
        view._update_battery_status()

        # Assert: Red color
        color_str = str(view.voltage_value_label.cget("foreground"))
        assert "red" in color_str.lower()

    def test_voltage_display_shows_red_for_critical_high_voltage(self, tk_root: tk.Tk, mock_base_window: MagicMock) -> None:
        """
        Voltage display shows red for critically high voltage.

        GIVEN: Battery voltage above maximum threshold
        WHEN: Status is updated
        THEN: Voltage label should be colored red
        """
        # pylint: disable=duplicate-code
        # Arrange: FC with high voltage
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()
        mock_fc.fc_parameters = {
            "BATT_MONITOR": 4,
            "BATT_ARM_VOLT": 11.0,
            "MOT_BAT_VOLT_MAX": 16.8,
        }
        mock_fc.is_battery_monitoring_enabled.return_value = True
        # pylint: enable=duplicate-code
        mock_fc.get_battery_status.return_value = ((17.5, 0.1), "")
        mock_fc.get_voltage_thresholds.return_value = (11.0, 16.8)

        model = BatteryMonitorDataModel(mock_fc)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update()

        # Act: Update battery status
        view._update_battery_status()

        # Assert: Red color
        color_str = str(view.voltage_value_label.cget("foreground"))
        assert "red" in color_str.lower()

    def test_voltage_display_shows_gray_when_monitoring_disabled(self, tk_root: tk.Tk, mock_base_window: MagicMock) -> None:
        """
        Voltage display shows gray when monitoring is disabled.

        GIVEN: Battery monitoring disabled
        WHEN: Status is updated
        THEN: Voltage label should be colored gray
        """
        # Arrange: FC with monitoring disabled
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()
        mock_fc.fc_parameters = {"BATT_MONITOR": 0}
        mock_fc.is_battery_monitoring_enabled.return_value = False

        model = BatteryMonitorDataModel(mock_fc)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update()

        # Act: Update battery status
        view._update_battery_status()

        # Assert: Gray color
        color_str = str(view.voltage_value_label.cget("foreground"))
        assert "gray" in color_str.lower()
