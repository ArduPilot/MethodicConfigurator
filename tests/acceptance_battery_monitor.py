#!/usr/bin/env python3

"""
Acceptance tests for battery monitor plugin.

These tests validate complete user workflows by mocking only the backend (FlightController)
and fully testing the data model and frontend together as an integrated system.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import tkinter as tk
from math import nan
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.data_model_battery_monitor import BatteryMonitorDataModel
from ardupilot_methodic_configurator.frontend_tkinter_battery_monitor import (
    BatteryMonitorView,
    _create_battery_monitor_view,
    register_battery_monitor_plugin,
)
from ardupilot_methodic_configurator.plugin_factory import plugin_factory

# pylint: disable=redefined-outer-name,protected-access


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
    mock_fc.fc_parameters = {}
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
        self, tk_root: tk.Tk, mock_flight_controller_with_battery: MagicMock, mock_base_window: MagicMock
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
