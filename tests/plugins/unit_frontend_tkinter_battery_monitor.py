#!/usr/bin/env python3

"""
Unit tests for battery monitor plugin internals.

These tests focus on low-level implementation details and edge cases to achieve
comprehensive code coverage. They test individual methods and internal behavior
that is not appropriate for acceptance or BDD tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.plugins.data_model_battery_monitor import BatteryMonitorDataModel
from ardupilot_methodic_configurator.plugins.frontend_tkinter_battery_monitor import (
    BatteryMonitorView,
    _create_battery_monitor_view,
    register_battery_monitor_plugin,
)
from ardupilot_methodic_configurator.plugins.plugin_factory import plugin_factory

# pylint: disable=redefined-outer-name,protected-access


@pytest.fixture
def mock_base_window(tk_root: tk.Tk) -> MagicMock:
    """Provide mock base window with real Tkinter root."""
    mock_window = MagicMock()
    mock_window.root = tk_root
    return mock_window


# pylint: disable=duplicate-code
@pytest.fixture
def mock_flight_controller() -> MagicMock:
    """Provide mock flight controller."""
    mock_fc = MagicMock()
    mock_fc.master = MagicMock()
    mock_fc.fc_parameters = {"BATT_MONITOR": 4}
    mock_fc.is_battery_monitoring_enabled.return_value = True
    mock_fc.get_battery_statuses.return_value = ({0: (12.4, 2.1)}, "")
    mock_fc.get_voltage_thresholds.return_value = (11.0, 16.8)
    return mock_fc


# pylint: enable=duplicate-code


class TestTimerLifecycle:
    """Test timer lifecycle and edge cases."""

    def test_on_activate_does_not_create_second_timer_if_already_running(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test on_activate doesn't create duplicate timers.

        GIVEN: View with timer already running
        WHEN: on_activate is called again
        THEN: Should not schedule a second timer
        """
        # Arrange: Create view and activate to start timer
        model = BatteryMonitorDataModel(mock_flight_controller)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()
        first_timer_id = view._timer_id
        tk_root.update_idletasks()

        # Act: Activate again
        view.on_activate()

        # Assert: Timer ID should be unchanged (no new timer scheduled)
        assert view._timer_id == first_timer_id

    def test_on_activate_starts_timer_when_none_running(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test on_activate starts timer when none is running.

        GIVEN: View without active timer
        WHEN: on_activate is called
        THEN: Should schedule timer
        """
        # Arrange: Create view without starting timer
        model = BatteryMonitorDataModel(mock_flight_controller)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        assert view._timer_id is None

        # Act: Activate
        view.on_activate()

        # Assert: Timer should be scheduled
        assert view._timer_id is not None

    def test_periodic_update_does_not_update_when_connection_lost(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test periodic update skips battery update when connection lost.

        GIVEN: View with active timer
        WHEN: Connection is lost and periodic update is triggered
        THEN: refresh_connection_status should still return True (it always updates state)
              but battery status should be "N/A" indicating no connection
        """
        # Arrange: Create view initially connected
        mock_flight_controller.is_connected.return_value = True
        model = BatteryMonitorDataModel(mock_flight_controller)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()
        tk_root.update_idletasks()

        # Simulate connection loss
        mock_flight_controller.is_connected.return_value = False
        mock_flight_controller.get_battery_statuses.return_value = (None, "Not connected")

        # Act: Trigger periodic update
        view._periodic_update()
        tk_root.update_idletasks()

        # Assert: Timer should still be scheduled (continuous monitoring)
        assert view._timer_id is not None
        # Battery display should show N/A when disconnected
        assert "N/A" in view._battery_rows[0][1].cget("text")

    def test_periodic_update_clears_battery_readings_when_fc_disconnected(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test periodic update skips battery status update when FC is disconnected.

        GIVEN: View with disconnected flight controller (master = None)
        WHEN: _periodic_update is called
        THEN: Should update unavailable readings but continue scheduling
        """
        # Arrange: Create view with disconnected FC
        mock_flight_controller.master = None  # Disconnected
        model = BatteryMonitorDataModel(mock_flight_controller)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update_idletasks()

        # Act: Trigger periodic update
        with patch.object(view, "_update_battery_status") as mock_update:
            view._periodic_update()

            # Assert: Should clear stale readings when disconnected
            mock_update.assert_called_once_with()
            # Timer should still be scheduled for next attempt
            assert view._timer_id is not None

    def test_on_activate_refreshes_unavailable_readings_when_fc_disconnected(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test on_activate skips initial battery update when FC is disconnected.

        GIVEN: View with disconnected flight controller
        WHEN: on_activate is called
        THEN: Should update unavailable readings but start timer
        """
        # Arrange: Create view with disconnected FC
        mock_flight_controller.master = None  # Disconnected
        model = BatteryMonitorDataModel(mock_flight_controller)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update_idletasks()

        # Act: Activate the view
        with patch.object(view, "_update_battery_status") as mock_update:
            view.on_activate()

            # Assert: Should clear stale readings when disconnected
            mock_update.assert_called_once_with()
            # But timer should still be started for future attempts
            assert view._timer_id is not None

    def test_on_deactivate_handles_no_active_timer_gracefully(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test on_deactivate handles case when no timer is active.

        GIVEN: View without active timer
        WHEN: on_deactivate is called
        THEN: Should not raise exception
        """
        # Arrange: Create view without starting timer
        model = BatteryMonitorDataModel(mock_flight_controller)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        assert view._timer_id is None

        # Act & Assert: Should not raise
        view.on_deactivate()
        assert view._timer_id is None

    def test_destroy_handles_no_active_timer_gracefully(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test destroy handles case when no timer is active.

        GIVEN: View without active timer
        WHEN: destroy is called
        THEN: Should clean up without exception
        """
        # Arrange: Create view without starting timer
        model = BatteryMonitorDataModel(mock_flight_controller)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        assert view._timer_id is None

        # Act & Assert: Should not raise
        view.destroy()


class TestModuleLevelFunctions:
    """Test module-level functions for coverage."""

    def test_create_battery_monitor_view_factory_function(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test _create_battery_monitor_view factory function.

        GIVEN: Valid arguments for view creation
        WHEN: _create_battery_monitor_view is called
        THEN: Should return BatteryMonitorView instance
        """
        # Arrange: Create data model
        model = BatteryMonitorDataModel(mock_flight_controller)

        # Act: Call factory function
        view = _create_battery_monitor_view(tk_root, model, mock_base_window)

        # Assert: Should return view instance
        assert isinstance(view, BatteryMonitorView)
        assert view.model == model

    def test_register_battery_monitor_plugin_registers_with_factory(self) -> None:
        """
        Test register_battery_monitor_plugin registers plugin.

        GIVEN: Clean plugin factory
        WHEN: register_battery_monitor_plugin is called
        THEN: Should register 'battery_monitor' plugin
        """
        # Act: Register plugin
        register_battery_monitor_plugin()

        # Assert: Should be registered
        assert plugin_factory.is_registered("battery_monitor")
