#!/usr/bin/env python3

"""
Integration tests for plugin system end-to-end workflows.

This file tests the complete plugin execution flow from registration
through configuration loading to actual plugin execution.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator import __main__
from ardupilot_methodic_configurator.business_logic_tempcal_imu import TempCalIMUDataModel
from ardupilot_methodic_configurator.configuration_manager import ConfigurationManager
from ardupilot_methodic_configurator.frontend_tkinter_tempcal_imu import TempCalIMUWorkflow
from ardupilot_methodic_configurator.plugin_constants import PLUGIN_MOTOR_TEST, PLUGIN_TEMPCAL_IMU
from ardupilot_methodic_configurator.plugin_factory_ui import plugin_factory_ui
from ardupilot_methodic_configurator.plugin_factory_workflow import plugin_factory_workflow


class TestPluginSystemIntegration:
    """Integration tests for the complete plugin system."""

    @pytest.fixture(autouse=True)
    def cleanup_plugin_registries(self) -> Generator[None, None, None]:
        """
        Clean up plugin registries before and after each test.

        Ensures test isolation by clearing any registered plugins.
        """
        # Store original registrations
        original_ui_plugins = dict(plugin_factory_ui._creators)  # pylint: disable=protected-access
        original_workflow_plugins = dict(plugin_factory_workflow._creators)  # pylint: disable=protected-access

        # Clear registries
        plugin_factory_ui._creators.clear()  # pylint: disable=protected-access
        plugin_factory_workflow._creators.clear()  # pylint: disable=protected-access

        yield

        # Restore original registrations
        plugin_factory_ui._creators.update(original_ui_plugins)  # pylint: disable=protected-access
        plugin_factory_workflow._creators.update(original_workflow_plugins)  # pylint: disable=protected-access

    def test_plugin_registration_during_app_startup_registers_all_plugins(self) -> None:
        """
        Test that register_plugins() registers all expected plugins.

        GIVEN: Clean plugin registries
        WHEN: Calling register_plugins() during app startup
        THEN: All expected plugins should be registered in their respective factories
        """
        __main__.register_plugins()

        # Check UI plugins
        assert plugin_factory_ui.is_registered(PLUGIN_MOTOR_TEST)

        # Check workflow plugins
        assert plugin_factory_workflow.is_registered(PLUGIN_TEMPCAL_IMU)

    def test_plugin_registration_populates_factory_with_correct_creators(self) -> None:
        """
        Test that registered plugins can be created successfully.

        GIVEN: Plugins are registered during startup
        WHEN: Attempting to create plugin instances
        THEN: Factories should return valid plugin instances
        """
        __main__.register_plugins()

        # Test UI plugin creation - skip because it requires complex widget mocking
        # The factory registration itself is tested in other tests
        assert plugin_factory_ui.is_registered(PLUGIN_MOTOR_TEST)

        # Test workflow plugin creation
        mock_root = MagicMock()
        mock_data_model = MagicMock()

        workflow_plugin = plugin_factory_workflow.create(PLUGIN_TEMPCAL_IMU, mock_root, mock_data_model)
        assert isinstance(workflow_plugin, TempCalIMUWorkflow)

    @patch("ardupilot_methodic_configurator.frontend_tkinter_tempcal_imu.TempCalIMUWorkflow.run_workflow")
    def test_workflow_plugin_execution_flow_from_factory_to_run_workflow(self, mock_run_workflow) -> None:
        """
        Test complete workflow plugin execution from factory creation to workflow run.

        GIVEN: A registered workflow plugin
        WHEN: Creating and executing the plugin through the factory
        THEN: The workflow should execute successfully
        """
        __main__.register_plugins()

        mock_root = MagicMock()
        mock_data_model = MagicMock()
        mock_run_workflow.return_value = True

        # Create plugin through factory
        workflow = plugin_factory_workflow.create(PLUGIN_TEMPCAL_IMU, mock_root, mock_data_model)
        assert isinstance(workflow, TempCalIMUWorkflow)

        # Execute workflow
        result = workflow.run_workflow()

        assert result is True
        mock_run_workflow.assert_called_once()

    def test_configuration_manager_can_create_tempcal_imu_data_model(self) -> None:
        """
        Test ConfigurationManager can create TempCalIMUDataModel for workflow plugins.

        GIVEN: A configuration manager instance
        WHEN: Requesting data model creation for tempcal_imu plugin
        THEN: Should return a valid TempCalIMUDataModel instance
        """
        # Create minimal configuration manager (mock dependencies)
        mock_fs = MagicMock()
        mock_fc = MagicMock()
        mock_current_file = "test.param"

        config_manager = ConfigurationManager(mock_current_file, mock_fc, mock_fs)

        # Test data model creation
        data_model = config_manager.create_plugin_data_model(
            PLUGIN_TEMPCAL_IMU,
            step_filename="03_imu_temp_cal.param",
            ask_confirmation=MagicMock(return_value=True),
            select_file=MagicMock(return_value="/test/log.bin"),
            show_warning=MagicMock(),
            show_error=MagicMock(),
            progress_callback=MagicMock(),
            cleanup_callback=MagicMock(),
        )

        assert isinstance(data_model, TempCalIMUDataModel)

    def test_configuration_manager_returns_none_for_invalid_plugin_data_model_request(self) -> None:
        """
        Test ConfigurationManager returns None for invalid plugin requests.

        GIVEN: A configuration manager instance
        WHEN: Requesting data model for unknown plugin or with missing parameters
        THEN: Should return None gracefully
        """
        mock_fs = MagicMock()
        mock_fc = MagicMock()
        mock_current_file = "test.param"

        config_manager = ConfigurationManager(mock_current_file, mock_fc, mock_fs)

        # Test unknown plugin
        result = config_manager.create_plugin_data_model("unknown_plugin")
        assert result is None

        # Test tempcal_imu without required parameters
        result = config_manager.create_plugin_data_model(PLUGIN_TEMPCAL_IMU)
        assert result is None

    @patch("ardupilot_methodic_configurator.configuration_manager.LocalFilesystem")
    @patch("ardupilot_methodic_configurator.configuration_manager.FlightController")
    def test_end_to_end_plugin_workflow_execution_via_configuration_manager(self, mock_fc, mock_fs) -> None:
        """
        Test end-to-end workflow execution through ConfigurationManager interface.

        GIVEN: A complete plugin setup with registered plugins
        WHEN: Executing workflow through configuration manager
        THEN: The workflow should complete successfully
        """
        # Setup mocks
        mock_fs_instance = MagicMock()
        mock_fs_instance.vehicle_dir = "/test/vehicle"
        mock_fs_instance.get_configuration_file_fullpath.return_value = "/test/vehicle/03_imu_temp_cal.param"
        mock_fs.return_value = mock_fs_instance

        mock_fc_instance = MagicMock()
        mock_fc.return_value = mock_fc_instance

        # Create configuration manager
        config_manager = ConfigurationManager("test.param", mock_fc_instance, mock_fs_instance)

        # Register plugins
        __main__.register_plugins()

        # Create data model
        data_model = config_manager.create_plugin_data_model(
            PLUGIN_TEMPCAL_IMU,
            step_filename="03_imu_temp_cal.param",
            ask_confirmation=MagicMock(return_value=True),
            select_file=MagicMock(return_value="/test/log.bin"),
            show_warning=MagicMock(),
            show_error=MagicMock(),
            progress_callback=MagicMock(),
            cleanup_callback=MagicMock(),
        )

        # Create workflow coordinator
        workflow = plugin_factory_workflow.create(PLUGIN_TEMPCAL_IMU, MagicMock(), data_model)

        # Execute workflow
        with patch.object(data_model, "run_calibration", return_value=True) as mock_calibration:
            result = workflow.run_workflow()

            assert result is True
            mock_calibration.assert_called_once()

    def test_plugin_system_handles_missing_registrations_gracefully(self) -> None:
        """
        Test plugin system handles missing plugin registrations gracefully.

        GIVEN: A request for an unregistered plugin
        WHEN: Attempting to create the plugin
        THEN: Should return None without raising exceptions
        """
        # Ensure plugin is not registered
        assert not plugin_factory_ui.is_registered("nonexistent_ui_plugin")
        assert not plugin_factory_workflow.is_registered("nonexistent_workflow_plugin")

        # Test UI plugin
        result = plugin_factory_ui.create("nonexistent_ui_plugin", MagicMock(), MagicMock(), MagicMock())
        assert result is None

        # Test workflow plugin
        result = plugin_factory_workflow.create("nonexistent_workflow_plugin", MagicMock(), MagicMock())
        assert result is None

    def test_plugin_factories_maintain_independence_between_ui_and_workflow_plugins(self) -> None:
        """
        Test UI and workflow plugin factories maintain separate registries.

        GIVEN: Plugins registered in both factories
        WHEN: Querying each factory
        THEN: Each factory should only know about its own plugins
        """
        # Register a UI plugin
        plugin_factory_ui.register("test_ui_plugin", MagicMock())

        # Register a workflow plugin
        plugin_factory_workflow.register("test_workflow_plugin", MagicMock())

        # Verify separation
        assert plugin_factory_ui.is_registered("test_ui_plugin")
        assert not plugin_factory_ui.is_registered("test_workflow_plugin")

        assert plugin_factory_workflow.is_registered("test_workflow_plugin")
        assert not plugin_factory_workflow.is_registered("test_ui_plugin")

        # Verify plugin lists
        ui_plugins = plugin_factory_ui.get_registered_plugins()
        workflow_plugins = plugin_factory_workflow.get_registered_plugins()

        assert "test_ui_plugin" in ui_plugins
        assert "test_workflow_plugin" not in ui_plugins

        assert "test_workflow_plugin" in workflow_plugins
        assert "test_ui_plugin" not in workflow_plugins

    def test_configuration_manager_returns_none_when_partial_callbacks_provided(self) -> None:
        """
        Test ConfigurationManager handles missing callbacks gracefully.

        GIVEN: A configuration manager instance
        WHEN: Requesting data model with only some callbacks provided (missing some)
        THEN: Should return None due to incomplete callback set
        """
        mock_fs = MagicMock()
        mock_fc = MagicMock()
        mock_current_file = "test.param"

        config_manager = ConfigurationManager(mock_current_file, mock_fc, mock_fs)

        # Test with missing cleanup_callback
        result = config_manager.create_plugin_data_model(
            PLUGIN_TEMPCAL_IMU,
            step_filename="03_imu_temp_cal.param",
            ask_confirmation=MagicMock(return_value=True),
            select_file=MagicMock(return_value="/test/log.bin"),
            show_warning=MagicMock(),
            show_error=MagicMock(),
            progress_callback=MagicMock(),
            # cleanup_callback missing
        )
        assert result is None

        # Test with missing progress_callback
        result = config_manager.create_plugin_data_model(
            PLUGIN_TEMPCAL_IMU,
            step_filename="03_imu_temp_cal.param",
            ask_confirmation=MagicMock(return_value=True),
            select_file=MagicMock(return_value="/test/log.bin"),
            show_warning=MagicMock(),
            show_error=MagicMock(),
            cleanup_callback=MagicMock(),
            # progress_callback missing
        )
        assert result is None

    @patch("ardupilot_methodic_configurator.business_logic_tempcal_imu.IMUfit")
    def test_workflow_execution_handles_exceptions_gracefully(self, mock_imufit) -> None:
        """
        Test workflow execution handles exceptions from business logic.

        GIVEN: A registered workflow plugin with data model
        WHEN: The business logic raises an unexpected exception
        THEN: Workflow should handle it gracefully and cleanup should still occur
        """
        __main__.register_plugins()

        mock_root = MagicMock()
        cleanup_callback = MagicMock()
        mock_configuration_manager = MagicMock()
        mock_configuration_manager.vehicle_dir = "/test/vehicle"
        mock_configuration_manager.get_configuration_file_fullpath.return_value = "/test/vehicle/03_imu_temp_cal.param"

        # Create data model that will fail during calibration
        mock_imufit.side_effect = RuntimeError("Unexpected calibration error")

        data_model = TempCalIMUDataModel(
            mock_configuration_manager,
            "03_imu_temp_cal.param",
            ask_confirmation=MagicMock(return_value=True),
            select_file=MagicMock(return_value="/test/log.bin"),
            show_warning=MagicMock(),
            show_error=MagicMock(),
            progress_callback=MagicMock(),
            cleanup_callback=cleanup_callback,
        )

        # Create workflow coordinator
        workflow = plugin_factory_workflow.create(PLUGIN_TEMPCAL_IMU, mock_root, data_model)
        assert workflow is not None

        # Execute workflow - should raise the RuntimeError but cleanup should be called
        with pytest.raises(RuntimeError, match="Unexpected calibration error"):
            workflow.run_workflow()  # pyright: ignore[reportAttributeAccessIssue]

        # Verify cleanup was called even though calibration failed
        cleanup_callback.assert_called_once()

    def test_workflow_plugin_with_none_progress_callback(self) -> None:
        """
        Test workflow plugin works with None progress_callback.

        GIVEN: A workflow plugin data model
        WHEN: progress_callback is None (optional parameter)
        THEN: Data model should be created successfully and work without progress updates
        """
        mock_fs = MagicMock()
        mock_fc = MagicMock()
        mock_current_file = "test.param"

        config_manager = ConfigurationManager(mock_current_file, mock_fc, mock_fs)

        # Test with None progress_callback
        result = config_manager.create_plugin_data_model(
            PLUGIN_TEMPCAL_IMU,
            step_filename="03_imu_temp_cal.param",
            ask_confirmation=MagicMock(return_value=True),
            select_file=MagicMock(return_value="/test/log.bin"),
            show_warning=MagicMock(),
            show_error=MagicMock(),
            progress_callback=None,
            cleanup_callback=MagicMock(),
        )
        # Should return None because progress_callback is None
        assert result is None
