#!/usr/bin/env python3

"""
BDD (Behavior-Driven Development) tests for battery monitor plugin.

These tests describe complete user stories and scenarios that span multiple features.
Unlike unit tests (which test individual methods) and acceptance tests (which test
data model + frontend integration), BDD tests focus on end-to-end user journeys
and business value delivered to the user.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import tkinter as tk
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.data_model_battery_monitor import BatteryMonitorDataModel
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict
from ardupilot_methodic_configurator.frontend_tkinter_battery_monitor import BatteryMonitorView

# pylint: disable=redefined-outer-name,protected-access


# pylint: disable=duplicate-code
@pytest.fixture
def tk_root() -> tk.Tk:
    """Provide a real Tkinter root window for BDD testing."""
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


# pylint: enable=duplicate-code


class TestPreFlightBatteryCheck:
    """
    User Story: As a drone pilot, I want to check my battery status before flight.

    So that I can ensure safe operation and avoid mid-flight battery failures.
    """

    def test_pilot_checks_battery_before_first_flight_of_the_day(self, tk_root: tk.Tk, mock_base_window: MagicMock) -> None:
        """
        Scenario: Pilot performs pre-flight battery check.

        GIVEN: A pilot connects their flight controller with a fully charged 4S LiPo battery (16.8V)
        WHEN: They open the battery configuration step
        THEN: They should see the battery voltage displayed as 16.8V
        AND: The display should be green indicating safe voltage
        AND: They should see minimal current draw (standby mode)
        AND: They can confidently proceed with flight
        """
        # pylint: disable=duplicate-code
        # Given: Flight controller connected with fully charged battery
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()  # Connected
        mock_fc.fc_parameters = {
            "BATT_MONITOR": 4,
            "BATT_ARM_VOLT": 11.0,
            "MOT_BAT_VOLT_MAX": 16.8,
        }
        mock_fc.is_battery_monitoring_enabled.return_value = True
        # pylint: enable=duplicate-code
        mock_fc.get_battery_status.return_value = ((16.7, 0.3), "")  # Just below max = safe
        mock_fc.get_voltage_thresholds.return_value = (11.0, 16.8)
        mock_fc.request_periodic_battery_status.return_value = None

        # When: Pilot opens battery monitor
        model = BatteryMonitorDataModel(mock_fc)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        # Then: Display shows safe, fully charged status
        assert "16.7" in view.voltage_value_label.cget("text")
        assert "0.3" in view.current_value_label.cget("text")
        assert model.get_battery_status_color() == "green"

    def test_pilot_discovers_battery_is_too_low_for_safe_flight(self, tk_root: tk.Tk, mock_base_window: MagicMock) -> None:
        """
        Scenario: Pilot discovers low battery before attempting flight.

        GIVEN: A pilot connects their flight controller with a partially discharged battery (10.8V)
        WHEN: They open the battery configuration step
        THEN: They should see the battery voltage displayed as 10.8V
        AND: The display should be RED indicating critical voltage
        AND: They should understand the battery needs charging before flight
        AND: This prevents a potentially dangerous flight attempt
        """
        # pylint: disable=duplicate-code
        # Given: Flight controller with low battery (below BATT_ARM_VOLT)
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()  # Connected
        mock_fc.fc_parameters = {
            "BATT_MONITOR": 4,
            "BATT_ARM_VOLT": 11.0,
            "MOT_BAT_VOLT_MAX": 16.8,
        }
        mock_fc.is_battery_monitoring_enabled.return_value = True
        # pylint: enable=duplicate-code
        mock_fc.get_battery_status.return_value = ((10.8, 0.2), "")  # Below arming voltage
        mock_fc.get_voltage_thresholds.return_value = (11.0, 16.8)
        mock_fc.request_periodic_battery_status.return_value = None

        # When: Pilot opens battery monitor
        model = BatteryMonitorDataModel(mock_fc)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        # Then: Display shows critical warning
        assert "10.8" in view.voltage_value_label.cget("text")
        assert model.get_battery_status_color() == "red"


class TestMotorTestingScenario:
    """
    User Story: As a drone operator performing motor tests.

    I want to monitor battery voltage and current in real-time so that I can detect problems
    and avoid battery damage during high-current testing.
    """

    def test_operator_monitors_battery_during_progressive_motor_test(
        self, tk_root: tk.Tk, mock_base_window: MagicMock
    ) -> None:
        """
        Scenario: Operator performs progressive motor test while monitoring battery.

        GIVEN: An operator has the battery monitor visible during motor testing
        WHEN: They progressively increase throttle (idle → 50% → 100%)
        THEN: They should see voltage drop from 12.4V → 12.1V → 11.8V
        AND: They should see current increase from 2A → 15A → 28A
        AND: Display should remain green throughout (above safety threshold)
        AND: They can confirm motors are drawing expected current
        """
        # pylint: disable=duplicate-code
        # Given: Battery monitor active during motor test
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()  # Connected
        mock_fc.fc_parameters = {
            "BATT_MONITOR": 4,
            "BATT_ARM_VOLT": 11.0,
            "MOT_BAT_VOLT_MAX": 16.8,
        }
        mock_fc.is_battery_monitoring_enabled.return_value = True
        # pylint: enable=duplicate-code
        mock_fc.get_voltage_thresholds.return_value = (11.0, 16.8)
        mock_fc.get_battery_status.return_value = ((12.4, 2.0), "")  # Initial state
        mock_fc.request_periodic_battery_status.return_value = None

        model = BatteryMonitorDataModel(mock_fc)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display

        # When: Idle state
        mock_fc.get_battery_status.return_value = ((12.4, 2.0), "")
        view._periodic_update()
        tk_root.update()

        # Then: Idle state shows normal values
        assert "12.4" in view.voltage_value_label.cget("text")
        assert "2.0" in view.current_value_label.cget("text")
        assert model.get_battery_status_color() == "green"

        # When: 50% throttle
        mock_fc.get_battery_status.return_value = ((12.1, 15.0), "")
        view._periodic_update()
        tk_root.update()

        # Then: Moderate load shows voltage drop and current increase
        assert "12.1" in view.voltage_value_label.cget("text")
        assert "15.0" in view.current_value_label.cget("text")
        assert model.get_battery_status_color() == "green"

        # When: Full throttle
        mock_fc.get_battery_status.return_value = ((11.8, 28.0), "")
        view._periodic_update()
        tk_root.update()

        # Then: High load shows significant voltage sag but still safe
        assert "11.8" in view.voltage_value_label.cget("text")
        assert "28.0" in view.current_value_label.cget("text")
        assert model.get_battery_status_color() == "green"

    def test_operator_detects_excessive_voltage_sag_during_motor_test(
        self, tk_root: tk.Tk, mock_base_window: MagicMock
    ) -> None:
        """
        Scenario: Operator detects problematic voltage sag indicating battery issues.

        GIVEN: An operator is testing motors with a worn-out battery
        WHEN: They apply moderate throttle (50%)
        THEN: Battery voltage drops below safety threshold (10.5V at only 15A)
        AND: Display turns RED to warn the operator
        AND: Operator can identify the battery needs replacement
        AND: This prevents using a weak battery in actual flight
        """
        # Given: Motor test with worn battery (high internal resistance)
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()  # Connected
        mock_fc.fc_parameters = {
            "BATT_MONITOR": 4,
            "BATT_ARM_VOLT": 11.0,
            "MOT_BAT_VOLT_MAX": 16.8,
        }
        mock_fc.is_battery_monitoring_enabled.return_value = True
        mock_fc.get_voltage_thresholds.return_value = (11.0, 16.8)
        mock_fc.get_battery_status.return_value = ((12.4, 2.0), "")  # Initial state
        mock_fc.request_periodic_battery_status.return_value = None

        model = BatteryMonitorDataModel(mock_fc)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display

        # When: Moderate load causes excessive voltage sag
        mock_fc.get_battery_status.return_value = ((10.5, 15.0), "")  # Abnormal sag
        view._periodic_update()
        tk_root.update()

        # Then: Critical warning alerts operator to battery problem
        assert "10.5" in view.voltage_value_label.cget("text")
        assert model.get_battery_status_color() == "red"


class TestFieldConfigurationScenario:
    """
    User Story: As a field technician, I want to configure battery parameters.

    And see immediate feedback so that I can verify settings are correct
    before the first flight.
    """

    def test_technician_verifies_battery_monitoring_is_properly_configured(
        self, tk_root: tk.Tk, mock_base_window: MagicMock
    ) -> None:
        """
        Scenario: Technician verifies battery sensor configuration.

        GIVEN: A technician is configuring a new drone in the field
        WHEN: They navigate to the battery configuration step
        THEN: They should see live battery readings (12.4V, 2.1A)
        AND: Green color confirms monitoring is working correctly
        AND: They can proceed with remaining configuration steps
        """
        # Given: Technician configuring new drone
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()  # Connected
        mock_fc.fc_parameters = {
            "BATT_MONITOR": 4,  # Analog sensor configured
            "BATT_ARM_VOLT": 11.0,
            "MOT_BAT_VOLT_MAX": 16.8,
        }
        mock_fc.is_battery_monitoring_enabled.return_value = True
        mock_fc.get_battery_status.return_value = ((12.4, 2.1), "")
        mock_fc.get_voltage_thresholds.return_value = (11.0, 16.8)
        mock_fc.request_periodic_battery_status.return_value = None

        # When: Technician opens battery configuration
        model = BatteryMonitorDataModel(mock_fc)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        # Then: Live readings confirm proper configuration
        assert "12.4" in view.voltage_value_label.cget("text")
        assert "2.1" in view.current_value_label.cget("text")
        assert model.get_battery_status_color() == "green"

    def test_technician_discovers_battery_monitoring_not_configured(self, tk_root: tk.Tk, mock_base_window: MagicMock) -> None:
        """
        Scenario: Technician discovers battery monitoring needs to be enabled.

        GIVEN: A technician is reviewing configuration of a customer's drone
        WHEN: They navigate to the battery configuration step
        THEN: They should see "Disabled" status
        AND: Gray color indicates monitoring is not active
        AND: They know to configure BATT_MONITOR parameter
        """
        # Given: Drone with battery monitoring not configured
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()  # Connected
        mock_fc.fc_parameters = {
            "BATT_MONITOR": 0,  # Disabled
        }
        mock_fc.is_battery_monitoring_enabled.return_value = False

        # When: Technician checks battery configuration
        model = BatteryMonitorDataModel(mock_fc)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        # Then: Display clearly indicates monitoring is disabled
        assert "Disabled" in view.voltage_value_label.cget("text")
        assert model.get_battery_status_color() == "gray"


class TestConnectionReliabilityScenario:  # pylint: disable=too-few-public-methods
    """
    User Story: As a user working with intermittent telemetry connections.

    I want the battery monitor to handle disconnections gracefully so that
    I don't lose my place in configuration when connection is temporarily lost.
    """

    def test_user_experiences_brief_telemetry_dropout_during_configuration(
        self, tk_root: tk.Tk, mock_base_window: MagicMock
    ) -> None:
        """
        Scenario: User continues working despite brief connection loss.

        GIVEN: A user is monitoring battery with active telemetry connection
        WHEN: USB cable is momentarily unplugged and reconnected
        THEN: Display should show "Disabled" during disconnection
        AND: Should automatically resume showing battery data when reconnected
        AND: User can continue their work without restarting the application
        """
        # Given: Active battery monitoring
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()  # Connected
        mock_fc.fc_parameters = {
            "BATT_MONITOR": 4,
            "BATT_ARM_VOLT": 11.0,
            "MOT_BAT_VOLT_MAX": 16.8,
        }
        mock_fc.is_battery_monitoring_enabled.return_value = True
        mock_fc.get_battery_status.return_value = ((12.4, 2.1), "")
        mock_fc.get_voltage_thresholds.return_value = (11.0, 16.8)
        mock_fc.request_periodic_battery_status.return_value = None

        model = BatteryMonitorDataModel(mock_fc)
        view = BatteryMonitorView(tk_root, model, mock_base_window)
        view.on_activate()  # Start timer and update display
        tk_root.update()

        # Verify: Initial connection shows data
        assert "12.4" in view.voltage_value_label.cget("text")

        # When: Connection lost
        mock_fc.is_battery_monitoring_enabled.return_value = False
        view._periodic_update()
        tk_root.update()

        # Then: Display shows disabled state
        assert "Disabled" in view.voltage_value_label.cget("text")

        # When: Connection restored
        mock_fc.is_battery_monitoring_enabled.return_value = True
        mock_fc.get_battery_status.return_value = ((12.3, 2.0), "")  # Slightly changed
        view._periodic_update()
        tk_root.update()

        # Then: Display automatically resumes showing data
        assert "12.3" in view.voltage_value_label.cget("text")
        assert view._timer_id is not None  # Updates continue


class TestBoundaryConditionScenarios:
    """
    User Story: As a power user testing edge cases.

    I want the battery monitor to handle boundary conditions correctly so that I can trust the readings
    at critical voltage thresholds.
    """

    def test_user_tests_exact_minimum_arming_voltage_threshold(self, tk_root: tk.Tk, mock_base_window: MagicMock) -> None:
        """
        Scenario: User tests battery at exact minimum arming voltage.

        GIVEN: A user wants to determine the exact minimum safe voltage
        WHEN: Battery voltage equals BATT_ARM_VOLT (11.0V exactly)
        THEN: Display should show RED (critical) because <= threshold
        AND: User understands this voltage is not safe for flight
        """
        # Given: Battery at exact threshold
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()  # Connected
        mock_fc.fc_parameters = {
            "BATT_MONITOR": 4,
            "BATT_ARM_VOLT": 11.0,
            "MOT_BAT_VOLT_MAX": 16.8,
        }
        mock_fc.is_battery_monitoring_enabled.return_value = True
        mock_fc.get_battery_status.return_value = ((11.0, 1.5), "")  # Exactly at threshold
        mock_fc.get_voltage_thresholds.return_value = (11.0, 16.8)
        mock_fc.request_periodic_battery_status.return_value = None

        # When: User views battery at exact threshold
        model = BatteryMonitorDataModel(mock_fc)
        BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update()

        # Then: Critical status shown (threshold is inclusive)
        assert model.get_voltage_status() == "critical"
        assert model.get_battery_status_color() == "red"

    def test_user_tests_just_above_minimum_arming_voltage_threshold(self, tk_root: tk.Tk, mock_base_window: MagicMock) -> None:
        """
        Scenario: User tests battery just above minimum threshold.

        GIVEN: A user wants to verify the safe voltage range
        WHEN: Battery voltage is just above BATT_ARM_VOLT (11.1V)
        THEN: Display should show GREEN (safe) because > threshold
        AND: User confirms this voltage is acceptable for arming
        """
        # Given: Battery just above threshold
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()  # Connected
        mock_fc.fc_parameters = {
            "BATT_MONITOR": 4,
            "BATT_ARM_VOLT": 11.0,
            "MOT_BAT_VOLT_MAX": 16.8,
        }
        mock_fc.is_battery_monitoring_enabled.return_value = True
        mock_fc.get_battery_status.return_value = ((11.1, 2.0), "")  # Just above threshold
        mock_fc.get_voltage_thresholds.return_value = (11.0, 16.8)
        mock_fc.request_periodic_battery_status.return_value = None

        # When: User views battery just above threshold
        model = BatteryMonitorDataModel(mock_fc)
        BatteryMonitorView(tk_root, model, mock_base_window)
        tk_root.update()

        # Then: Safe status shown
        assert model.get_voltage_status() == "safe"
        assert model.get_battery_status_color() == "green"


class TestBatteryParameterTuningWorkflow:
    """
    User Story: As a drone tuner, I want to adjust battery parameters and test them immediately.

    So that I can validate calibration changes without advancing through configuration steps.
    """

    def test_tuner_uploads_battery_calibration_and_verifies_readings(
        self, tk_root: tk.Tk, mock_base_window: MagicMock
    ) -> None:
        """
        Scenario: Tuner calibrates battery sensor and validates in real-time.

        GIVEN: A tuner is calibrating BATT_AMP_PERVLT (current sensor scaling)
        WHEN: They modify the parameter and upload it from the battery monitor plugin
        THEN: They should see the upload progress
        AND: The current reading should update to reflect the new calibration
        AND: They can immediately verify if the calibration is correct
        """
        # Given: Initial battery configuration with incorrect current reading
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()
        mock_fc.fc_parameters = {
            "BATT_MONITOR": 4,
            "BATT_AMP_PERVLT": 17.0,  # Old calibration
            "BATT_ARM_VOLT": 11.0,
        }
        mock_fc.is_battery_monitoring_enabled.return_value = True
        mock_fc.get_battery_status.return_value = ((12.4, 2.0), "")  # Incorrect current
        mock_fc.get_voltage_thresholds.return_value = (11.0, 16.8)

        # Mock parameter editor and upload workflow
        mock_param_editor = MagicMock()
        selected_params = ParDict({"BATT_AMP_PERVLT": Par(18.5)})  # New calibration
        mock_param_editor.ensure_upload_preconditions.return_value = True

        def simulate_successful_upload(_root, _workflow, _params, **_kwargs) -> None:
            # Simulate FC accepting new value and returning updated current
            mock_fc.fc_parameters["BATT_AMP_PERVLT"] = 18.5
            mock_fc.get_battery_status.return_value = ((12.4, 2.18), "")  # Corrected current

        mock_param_editor.upload_selected_params_workflow = MagicMock(side_effect=simulate_successful_upload)

        # Mock parameter table
        mock_param_table = MagicMock()
        mock_param_table.get_upload_selected_params.return_value = selected_params

        # Mock UI services
        mock_ui_services = MagicMock()
        mock_ui_services.upload_params_with_progress = MagicMock(side_effect=simulate_successful_upload)

        # pylint: disable=duplicate-code
        # Set up base window
        mock_base_window.gui_complexity = "normal"
        mock_base_window.parameter_editor_table = mock_param_table
        mock_base_window.show_only_differences = MagicMock()
        mock_base_window.show_only_differences.get.return_value = False

        # When: Tuner opens battery monitor and uploads calibration
        model = BatteryMonitorDataModel(mock_fc, mock_param_editor)
        view = BatteryMonitorView(tk_root, model, mock_base_window, ui_services=mock_ui_services)
        view.on_activate()
        tk_root.update()
        # pylint: enable=duplicate-code

        # Initial reading shows incorrect current
        assert "2.0" in view.current_value_label.cget("text")

        # Upload new calibration
        view._on_upload_button_clicked()

        # Then: Current reading updates to corrected value
        view._periodic_update()
        tk_root.update()
        assert "2.18" in view.current_value_label.cget("text")

    def test_tuner_adjusts_low_voltage_threshold_and_tests_immediately(
        self, tk_root: tk.Tk, mock_base_window: MagicMock
    ) -> None:
        """
        Scenario: Tuner lowers arming voltage threshold to extend flight time.

        GIVEN: A tuner wants to lower BATT_ARM_VOLT from 11.0V to 10.5V
        WHEN: They modify the parameter and upload from battery monitor
        THEN: The color-coding threshold should update immediately
        AND: They can test with current battery voltage to verify new threshold
        AND: This enables iterative tuning without navigation disruption
        """
        # Given: Conservative voltage threshold
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()
        mock_fc.fc_parameters = {
            "BATT_MONITOR": 4,
            "BATT_ARM_VOLT": 11.0,  # Conservative threshold
            "MOT_BAT_VOLT_MAX": 16.8,
        }
        mock_fc.is_battery_monitoring_enabled.return_value = True
        mock_fc.get_battery_status.return_value = ((10.7, 1.5), "")  # Below old threshold
        mock_fc.get_voltage_thresholds.return_value = (11.0, 16.8)

        # Mock parameter editor
        mock_param_editor = MagicMock()
        selected_params = ParDict({"BATT_ARM_VOLT": Par(10.5)})  # Lowered threshold
        mock_param_editor.ensure_upload_preconditions.return_value = True

        def simulate_threshold_update(_root, _workflow, _params, **_kwargs) -> None:
            # Simulate FC accepting new threshold
            mock_fc.fc_parameters["BATT_ARM_VOLT"] = 10.5
            mock_fc.get_voltage_thresholds.return_value = (10.5, 16.8)

        mock_param_editor.upload_selected_params_workflow = MagicMock(side_effect=simulate_threshold_update)

        # pylint: disable=duplicate-code
        mock_param_table = MagicMock()
        mock_param_table.get_upload_selected_params.return_value = selected_params

        mock_ui_services = MagicMock()
        mock_ui_services.upload_params_with_progress = MagicMock(side_effect=simulate_threshold_update)

        mock_base_window.gui_complexity = "normal"
        mock_base_window.parameter_editor_table = mock_param_table
        mock_base_window.show_only_differences = MagicMock()
        mock_base_window.show_only_differences.get.return_value = False

        # When: Battery at 10.7V (below old threshold, above new)
        model = BatteryMonitorDataModel(mock_fc, mock_param_editor)
        view = BatteryMonitorView(tk_root, model, mock_base_window, ui_services=mock_ui_services)
        view.on_activate()
        tk_root.update()
        # pylint: enable=duplicate-code

        # Then: Initially shows critical (below 11.0V)
        assert model.get_battery_status_color() == "red"

        # Upload new threshold
        view._on_upload_button_clicked()
        view._periodic_update()
        tk_root.update()

        # Then: Now shows safe (above 10.5V)
        assert model.get_battery_status_color() == "green"

    def test_tuner_handles_upload_error_gracefully(self, tk_root: tk.Tk, mock_base_window: MagicMock) -> None:
        """
        Scenario: Upload fails due to connection issue during tuning.

        GIVEN: A tuner is uploading battery parameters
        WHEN: The upload fails (FC disconnect, timeout, etc.)
        THEN: They should see an error message
        AND: The battery monitor should remain functional
        AND: They can retry the upload after fixing the issue
        """
        # pylint: disable=duplicate-code
        # Given: Setup for upload with potential failure
        mock_fc = MagicMock()
        mock_fc.master = MagicMock()
        mock_fc.fc_parameters = {"BATT_MONITOR": 4}
        mock_fc.is_battery_monitoring_enabled.return_value = True
        mock_fc.get_battery_status.return_value = ((12.4, 2.1), "")
        mock_fc.get_voltage_thresholds.return_value = (11.0, 16.8)  # Provide valid thresholds
        # pylint: enable=duplicate-code

        mock_param_editor = MagicMock()
        selected_params = ParDict({"BATT_CAPACITY": Par(6000)})
        mock_param_editor.ensure_upload_preconditions.return_value = True

        # Simulate upload failure
        def simulate_upload_failure(_root, _workflow, _params, **_kwargs) -> None:
            msg = "Flight controller disconnected"
            raise ConnectionError(msg)

        mock_param_editor.upload_selected_params_workflow = MagicMock(side_effect=simulate_upload_failure)

        mock_param_table = MagicMock()
        mock_param_table.get_upload_selected_params.return_value = selected_params

        mock_ui_services = MagicMock()
        mock_ui_services.upload_params_with_progress = MagicMock(side_effect=simulate_upload_failure)
        mock_ui_services.show_error = MagicMock()

        mock_base_window.gui_complexity = "normal"
        mock_base_window.parameter_editor_table = mock_param_table

        # When: Upload fails
        model = BatteryMonitorDataModel(mock_fc, mock_param_editor)
        view = BatteryMonitorView(tk_root, model, mock_base_window, ui_services=mock_ui_services)
        tk_root.update()

        # Then: Error is handled gracefully
        view._on_upload_button_clicked()

        # Verify error was shown to user
        mock_ui_services.show_error.assert_called_once()

        # Verify battery monitor still works
        view._periodic_update()
        tk_root.update()
        assert "12.4" in view.voltage_value_label.cget("text")
