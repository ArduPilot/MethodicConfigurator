#!/usr/bin/env python3

"""
Unit tests for battery monitor plugin internals.

These tests focus on low-level implementation details and edge cases to achieve
comprehensive code coverage. They test individual methods and internal behavior
that is not appropriate for acceptance or BDD tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.data_model_battery_monitor import BatteryMonitorDataModel
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.frontend_tkinter_battery_monitor import (
    BatteryMonitorView,
    _create_battery_monitor_view,
    register_battery_monitor_plugin,
)
from ardupilot_methodic_configurator.plugin_factory import plugin_factory

# pylint: disable=redefined-outer-name,protected-access


@pytest.fixture
def tk_root() -> tk.Tk:
    """Provide a real Tkinter root window for testing."""
    root = tk.Tk()
    root.withdraw()
    yield root
    with contextlib.suppress(tk.TclError):
        root.destroy()


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
    mock_fc.get_battery_status.return_value = ((12.4, 2.1), "")
    mock_fc.get_voltage_thresholds.return_value = (11.0, 16.8)
    return mock_fc


# pylint: enable=duplicate-code


class TestUploadButtonErrorHandling:
    """Test upload button error paths for code coverage."""

    def test_upload_button_click_when_ui_services_unavailable(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test upload button handles missing UI services gracefully.

        GIVEN: Battery monitor view without UI services
        WHEN: Upload button is clicked
        THEN: Should show error dialog and not crash
        """
        # Arrange: Create view with parameter editor but no UI services
        mock_param_editor = MagicMock()
        mock_base_window.ui = None  # Ensure no fallback to base_window.ui
        model = BatteryMonitorDataModel(mock_flight_controller, mock_param_editor)
        view = BatteryMonitorView(tk_root, model, mock_base_window, ui_services=None)
        tk_root.update()

        # Act & Assert: Click upload button - should show error
        with patch("ardupilot_methodic_configurator.frontend_tkinter_battery_monitor.showerror") as mock_error:
            view._on_upload_button_clicked()
            mock_error.assert_called_once()
            assert "UI services not available" in str(mock_error.call_args)

    def test_upload_button_click_when_parameter_table_unavailable(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test upload button handles missing parameter table.

        GIVEN: Battery monitor view without parameter editor table
        WHEN: Upload button is clicked
        THEN: Should show error and not proceed
        """
        # Arrange: Create view with UI services but no parameter_editor_table
        mock_param_editor = MagicMock()
        mock_ui_services = MagicMock()

        model = BatteryMonitorDataModel(mock_flight_controller, mock_param_editor)
        view = BatteryMonitorView(tk_root, model, mock_base_window, ui_services=mock_ui_services)

        # Ensure no parameter_editor_table attribute
        mock_base_window.gui_complexity = "simple"
        mock_base_window.parameter_editor_table = None
        tk_root.update()

        # Act & Assert: Click upload button - should show error
        with patch("ardupilot_methodic_configurator.frontend_tkinter_battery_monitor.showerror") as mock_error:
            view._on_upload_button_clicked()
            mock_error.assert_called_once()
            assert "Parameter editor not available" in str(mock_error.call_args)

    def test_upload_button_click_when_get_upload_selected_params_raises(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test upload button handles exception from get_upload_selected_params.

        GIVEN: Parameter table that raises exception
        WHEN: Upload button is clicked
        THEN: Should show error dialog and not crash
        """
        # Arrange: Create view with parameter table that raises
        mock_param_editor = MagicMock()
        mock_ui_services = MagicMock()
        mock_param_table = MagicMock()
        mock_param_table.get_upload_selected_params.side_effect = RuntimeError("Table error")

        model = BatteryMonitorDataModel(mock_flight_controller, mock_param_editor)
        view = BatteryMonitorView(tk_root, model, mock_base_window, ui_services=mock_ui_services)

        mock_base_window.gui_complexity = "normal"
        mock_base_window.parameter_editor_table = mock_param_table
        tk_root.update()

        # Act & Assert: Click upload button - should show error
        with patch("ardupilot_methodic_configurator.frontend_tkinter_battery_monitor.showerror") as mock_error:
            view._on_upload_button_clicked()
            mock_error.assert_called_once()
            assert "Table error" in str(mock_error.call_args)

    def test_upload_button_click_when_parameter_editor_missing(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test upload button handles missing parameter editor.

        GIVEN: Battery monitor view where model.parameter_editor becomes None
        WHEN: Upload button is clicked
        THEN: Should show error dialog
        """
        # Arrange: Create view with parameter editor, then remove it
        mock_param_editor = MagicMock()
        mock_ui_services = MagicMock()
        mock_param_table = MagicMock()
        mock_param_table.get_upload_selected_params.return_value = ParDict({"BATT_CAPACITY": Par(5200)})

        model = BatteryMonitorDataModel(mock_flight_controller, mock_param_editor)
        view = BatteryMonitorView(tk_root, model, mock_base_window, ui_services=mock_ui_services)

        mock_base_window.gui_complexity = "normal"
        mock_base_window.parameter_editor_table = mock_param_table

        # Remove parameter editor after view creation
        view.model.parameter_editor = None
        tk_root.update()

        # Act & Assert: Click upload button - should show error
        with patch("ardupilot_methodic_configurator.frontend_tkinter_battery_monitor.showerror") as mock_error:
            view._on_upload_button_clicked()
            mock_error.assert_called_once()
            assert "Parameter editor not available" in str(mock_error.call_args)

    def test_upload_button_click_when_preconditions_fail(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test upload button respects precondition check failure.

        GIVEN: Parameter editor that fails precondition check
        WHEN: Upload button is clicked
        THEN: Should not proceed with upload
        """
        # Arrange: Create view with failing preconditions
        mock_param_editor = MagicMock()
        mock_param_editor.ensure_upload_preconditions.return_value = False
        mock_ui_services = MagicMock()
        mock_param_table = MagicMock()
        mock_param_table.get_upload_selected_params.return_value = ParDict({"BATT_CAPACITY": Par(5200)})

        model = BatteryMonitorDataModel(mock_flight_controller, mock_param_editor)
        view = BatteryMonitorView(tk_root, model, mock_base_window, ui_services=mock_ui_services)

        mock_base_window.gui_complexity = "normal"
        mock_base_window.parameter_editor_table = mock_param_table
        tk_root.update()

        # Act: Click upload button
        view._on_upload_button_clicked()

        # Assert: Should check preconditions but not call upload
        mock_param_editor.ensure_upload_preconditions.assert_called_once()
        mock_ui_services.upload_params_with_progress.assert_not_called()

    def test_upload_button_refreshes_table_after_successful_upload(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test upload button refreshes parameter table after upload.

        GIVEN: Successful parameter upload
        WHEN: Upload completes
        THEN: Should refresh parameter editor table
        """
        # Arrange: Create view with all components
        mock_param_editor = MagicMock()
        mock_param_editor.ensure_upload_preconditions.return_value = True
        mock_ui_services = MagicMock()
        mock_param_table = MagicMock()
        mock_param_table.get_upload_selected_params.return_value = ParDict({"BATT_CAPACITY": Par(5200)})
        mock_show_only_diff = MagicMock()
        mock_show_only_diff.get.return_value = True

        model = BatteryMonitorDataModel(mock_flight_controller, mock_param_editor)
        view = BatteryMonitorView(tk_root, model, mock_base_window, ui_services=mock_ui_services)

        mock_base_window.gui_complexity = "normal"
        mock_base_window.parameter_editor_table = mock_param_table
        mock_base_window.show_only_differences = mock_show_only_diff
        tk_root.update()

        # Act: Click upload button
        view._on_upload_button_clicked()

        # Assert: Should refresh table with correct parameters
        mock_param_table.repopulate_table.assert_called_once_with(show_only_differences=True, gui_complexity="normal")

    def test_upload_button_refreshes_table_with_show_all_differences(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test upload button respects show_only_differences setting.

        GIVEN: Upload with show_only_differences = False
        WHEN: Upload completes
        THEN: Should refresh table with show_only_differences = False
        """
        # Arrange: Create view with show_only_differences = False
        mock_param_editor = MagicMock()
        mock_param_editor.ensure_upload_preconditions.return_value = True
        mock_ui_services = MagicMock()
        mock_param_table = MagicMock()
        mock_param_table.get_upload_selected_params.return_value = ParDict({"BATT_CAPACITY": Par(5200)})
        mock_show_only_diff = MagicMock()
        mock_show_only_diff.get.return_value = False

        model = BatteryMonitorDataModel(mock_flight_controller, mock_param_editor)
        view = BatteryMonitorView(tk_root, model, mock_base_window, ui_services=mock_ui_services)

        mock_base_window.gui_complexity = "simple"
        mock_base_window.parameter_editor_table = mock_param_table
        mock_base_window.show_only_differences = mock_show_only_diff
        tk_root.update()

        # Act: Click upload button
        view._on_upload_button_clicked()

        # Assert: Should refresh table with show_only_differences = False
        mock_param_table.repopulate_table.assert_called_once_with(show_only_differences=False, gui_complexity="simple")


class TestUploadSelectedParamsMethod:
    """Test upload_selected_params method edge cases."""

    def test_upload_selected_params_logs_error_when_ui_unavailable(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test upload_selected_params logs error when UI unavailable.

        GIVEN: View without UI services
        WHEN: upload_selected_params is called directly
        THEN: Should log error and return early
        """
        # Arrange: Create view without UI services
        mock_param_editor = MagicMock()
        mock_base_window.ui = None  # Ensure no fallback
        model = BatteryMonitorDataModel(mock_flight_controller, mock_param_editor)
        view = BatteryMonitorView(tk_root, model, mock_base_window, ui_services=None)
        tk_root.update()

        # Act & Assert: Call upload_selected_params
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_battery_monitor.showerror"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_battery_monitor.logging_error") as mock_log,
        ):
            view.upload_selected_params(ParDict())
            mock_log.assert_called_once()
            assert "UI services not available" in str(mock_log.call_args)

    def test_upload_selected_params_logs_error_when_param_editor_unavailable(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test upload_selected_params logs error when parameter editor unavailable.

        GIVEN: View without parameter editor
        WHEN: upload_selected_params is called directly
        THEN: Should log error and return early
        """
        # Arrange: Create view without parameter editor
        mock_ui_services = MagicMock()
        model = BatteryMonitorDataModel(mock_flight_controller, None)
        view = BatteryMonitorView(tk_root, model, mock_base_window, ui_services=mock_ui_services)
        tk_root.update()

        # Act & Assert: Call upload_selected_params
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_battery_monitor.showerror"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_battery_monitor.logging_error") as mock_log,
        ):
            view.upload_selected_params(ParDict())
            mock_log.assert_called_once()
            assert "Parameter editor not available" in str(mock_log.call_args)

    def test_upload_selected_params_handles_upload_exception(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test upload_selected_params handles exceptions during upload.

        GIVEN: Upload that raises exception
        WHEN: upload_selected_params is called
        THEN: Should show error and log it
        """
        # Arrange: Create view with upload that raises
        mock_param_editor = MagicMock()
        mock_ui_services = MagicMock()
        mock_ui_services.upload_params_with_progress.side_effect = RuntimeError("Upload failed")

        model = BatteryMonitorDataModel(mock_flight_controller, mock_param_editor)
        view = BatteryMonitorView(tk_root, model, mock_base_window, ui_services=mock_ui_services)
        tk_root.update()

        # Act & Assert: Call upload_selected_params
        with patch("ardupilot_methodic_configurator.frontend_tkinter_battery_monitor.logging_error") as mock_log:
            view.upload_selected_params(ParDict({"BATT_CAPACITY": Par(5200)}))
            mock_log.assert_called_once()
            mock_ui_services.show_error.assert_called_once()
            assert "Upload failed" in str(mock_log.call_args)


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
        model = BatteryMonitorDataModel(mock_flight_controller, None)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()
        first_timer_id = view._timer_id
        tk_root.update()

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
        model = BatteryMonitorDataModel(mock_flight_controller, None)
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
        model = BatteryMonitorDataModel(mock_flight_controller, None)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()
        tk_root.update()

        # Simulate connection loss
        mock_flight_controller.is_connected.return_value = False
        mock_flight_controller.get_battery_status.return_value = (None, "Not connected")

        # Act: Trigger periodic update
        view._periodic_update()
        tk_root.update()

        # Assert: Timer should still be scheduled (continuous monitoring)
        assert view._timer_id is not None
        # Battery display should show N/A when disconnected
        assert "N/A" in view.voltage_value_label.cget("text")

    def test_periodic_update_skips_battery_update_when_fc_disconnected(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test periodic update skips battery status update when FC is disconnected.

        GIVEN: View with disconnected flight controller (master = None)
        WHEN: _periodic_update is called
        THEN: Should skip _update_battery_status call but continue scheduling
        """
        # Arrange: Create view with disconnected FC
        mock_flight_controller.master = None  # Disconnected
        model = BatteryMonitorDataModel(mock_flight_controller, None)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update()

        # Act: Trigger periodic update
        with patch.object(view, "_update_battery_status") as mock_update:
            view._periodic_update()

            # Assert: Should not call _update_battery_status when disconnected
            mock_update.assert_not_called()
            # Timer should still be scheduled for next attempt
            assert view._timer_id is not None

    def test_on_activate_skips_initial_update_when_fc_disconnected(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test on_activate skips initial battery update when FC is disconnected.

        GIVEN: View with disconnected flight controller
        WHEN: on_activate is called
        THEN: Should skip initial _update_battery_status call but start timer
        """
        # Arrange: Create view with disconnected FC
        mock_flight_controller.master = None  # Disconnected
        model = BatteryMonitorDataModel(mock_flight_controller, None)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update()

        # Act: Activate the view
        with patch.object(view, "_update_battery_status") as mock_update:
            view.on_activate()

            # Assert: Should not call _update_battery_status when disconnected
            mock_update.assert_not_called()
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
        model = BatteryMonitorDataModel(mock_flight_controller, None)
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
        model = BatteryMonitorDataModel(mock_flight_controller, None)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        assert view._timer_id is None

        # Act & Assert: Should not raise
        view.destroy()


class TestParameterTableRefresh:
    """Test parameter table refresh fallback scenarios."""

    def test_upload_button_handles_missing_parameter_table_gracefully(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test upload button handles missing parameter_editor_table.

        GIVEN: Base window without parameter_editor_table attribute
        WHEN: Upload button is clicked
        THEN: Should show error and not crash
        """
        # Arrange: Create view with base window lacking parameter_editor_table
        mock_param_editor = MagicMock()
        mock_ui_services = MagicMock()

        model = BatteryMonitorDataModel(mock_flight_controller, mock_param_editor)
        view = BatteryMonitorView(tk_root, model, mock_base_window, ui_services=mock_ui_services)

        # Base window has no parameter_editor_table attribute
        mock_base_window.parameter_editor_table = None
        tk_root.update()

        # Act & Assert: Click upload button - should show error
        with patch("ardupilot_methodic_configurator.frontend_tkinter_battery_monitor.showerror") as mock_error:
            view._on_upload_button_clicked()
            mock_error.assert_called_once()
            assert "Parameter editor not available" in str(mock_error.call_args)

    def test_upload_button_handles_missing_show_only_differences(
        self, tk_root: tk.Tk, mock_flight_controller: MagicMock, mock_base_window: MagicMock
    ) -> None:
        """
        Test upload button handles missing show_only_differences attribute.

        GIVEN: Base window without show_only_differences
        WHEN: Upload completes and table refresh is attempted
        THEN: Should default to False for show_only_differences
        """
        # Arrange: Create view with parameter table but no show_only_differences
        mock_param_editor = MagicMock()
        mock_param_editor.ensure_upload_preconditions.return_value = True
        mock_ui_services = MagicMock()
        mock_param_table = MagicMock()
        mock_param_table.get_upload_selected_params.return_value = ParDict({"BATT_CAPACITY": Par(5200)})

        model = BatteryMonitorDataModel(mock_flight_controller, mock_param_editor)
        view = BatteryMonitorView(tk_root, model, mock_base_window, ui_services=mock_ui_services)

        # Base window has parameter_editor_table but no show_only_differences
        mock_base_window.parameter_editor_table = mock_param_table
        mock_base_window.gui_complexity = "normal"
        # Ensure show_only_differences attribute doesn't exist
        if hasattr(mock_base_window, "show_only_differences"):
            delattr(mock_base_window, "show_only_differences")
        tk_root.update()

        # Act: Click upload button
        view._on_upload_button_clicked()

        # Assert: Should refresh table with show_only_differences=False (default)
        mock_param_table.repopulate_table.assert_called_once_with(show_only_differences=False, gui_complexity="normal")


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
        model = BatteryMonitorDataModel(mock_flight_controller, None)

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
