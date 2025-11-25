#!/usr/bin/env python3

"""
Tests for IMU temperature calibration frontend workflow.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_tempcal_imu import (
    TempCalIMUWorkflow,
    create_tempcal_imu_workflow,
    register_tempcal_imu_plugin,
)
from ardupilot_methodic_configurator.plugin_constants import PLUGIN_TEMPCAL_IMU
from ardupilot_methodic_configurator.plugin_factory_workflow import plugin_factory_workflow


class TestTempCalIMUWorkflow:
    """Test suite for IMU temperature calibration frontend workflow."""

    @pytest.fixture
    def mock_root_window(self) -> MagicMock:
        """Create a mock root window for testing."""
        return MagicMock()

    @pytest.fixture
    def mock_data_model(self) -> MagicMock:
        """Create a mock data model for testing."""
        data_model = MagicMock()
        data_model.run_calibration.return_value = True
        return data_model

    @pytest.fixture
    def workflow(self, mock_root_window, mock_data_model) -> TempCalIMUWorkflow:
        """Create a workflow instance for testing."""
        return TempCalIMUWorkflow(mock_root_window, mock_data_model)

    def test_workflow_initialization_stores_dependencies(self, mock_root_window, mock_data_model) -> None:
        """
        Test workflow initialization stores provided dependencies.

        GIVEN: A root window and data model
        WHEN: Creating a TempCalIMUWorkflow instance
        THEN: Both dependencies should be stored for later use
        """
        workflow = TempCalIMUWorkflow(mock_root_window, mock_data_model)

        assert workflow.root_window is mock_root_window
        assert workflow.data_model is mock_data_model

    def test_user_successfully_runs_calibration_workflow(self, workflow, mock_data_model) -> None:
        """
        Test user can successfully run the calibration workflow.

        GIVEN: A user has initiated IMU temperature calibration
        WHEN: The workflow is executed
        THEN: The business logic should be invoked and return success status
        """
        result = workflow.run_workflow()

        assert result is True
        mock_data_model.run_calibration.assert_called_once()

    def test_workflow_returns_failure_when_calibration_fails(self, workflow, mock_data_model) -> None:
        """
        Test workflow returns failure status when calibration fails.

        GIVEN: A calibration workflow is prepared
        WHEN: The underlying calibration process fails
        THEN: The workflow should return False to indicate failure
        """
        mock_data_model.run_calibration.return_value = False

        result = workflow.run_workflow()

        assert result is False
        mock_data_model.run_calibration.assert_called_once()

    def test_workflow_delegates_all_logic_to_data_model(self, workflow, mock_data_model) -> None:
        """
        Test workflow properly delegates to business logic layer.

        GIVEN: A frontend workflow instance
        WHEN: User runs the calibration
        THEN: All business logic should be handled by the data model, not the frontend
        """
        workflow.run_workflow()

        # Verify delegation - the data model's run_calibration should be called
        mock_data_model.run_calibration.assert_called_once_with()

    def test_workflow_propagates_exceptions_from_data_model(self, workflow, mock_data_model) -> None:
        """
        Test workflow allows exceptions from data model to propagate.

        GIVEN: A workflow with a data model that raises an exception
        WHEN: Running the calibration workflow
        THEN: The exception should propagate to allow proper error handling upstream
        """
        mock_data_model.run_calibration.side_effect = RuntimeError("Calibration hardware error")

        with pytest.raises(RuntimeError, match="Calibration hardware error"):
            workflow.run_workflow()


class TestTempCalIMUWorkflowFactory:  # pylint: disable=too-few-public-methods
    """Test suite for workflow factory function."""

    def test_factory_creates_workflow_with_correct_dependencies(self) -> None:
        """
        Test factory function creates workflow with provided dependencies.

        GIVEN: A root window and data model
        WHEN: Using the factory function to create a workflow
        THEN: A properly configured TempCalIMUWorkflow should be returned
        """
        root_window = MagicMock()
        data_model = MagicMock()

        workflow = create_tempcal_imu_workflow(root_window, data_model)

        assert isinstance(workflow, TempCalIMUWorkflow)
        assert workflow.root_window is root_window
        assert workflow.data_model is data_model


class TestTempCalIMUPluginRegistration:
    """Test suite for plugin registration."""

    @pytest.fixture(autouse=True)
    def cleanup_plugin_registry(self) -> Generator[None, None, None]:
        """
        Clean up plugin registry before and after each test.

        This ensures test isolation by removing any registered plugins.
        """
        # Remove plugin if it exists before test
        if plugin_factory_workflow.is_registered(PLUGIN_TEMPCAL_IMU):
            # Access private attribute for cleanup (acceptable in tests)
            plugin_factory_workflow._creators.pop(PLUGIN_TEMPCAL_IMU, None)  # pylint: disable=protected-access

        yield

        # Clean up after test
        if plugin_factory_workflow.is_registered(PLUGIN_TEMPCAL_IMU):
            plugin_factory_workflow._creators.pop(PLUGIN_TEMPCAL_IMU, None)  # pylint: disable=protected-access

    def test_plugin_registration_adds_to_factory(self) -> None:
        """
        Test plugin registration adds tempcal_imu to the workflow factory.

        GIVEN: A clean plugin factory
        WHEN: Registering the tempcal_imu plugin
        THEN: The plugin should be available in the factory registry
        """
        register_tempcal_imu_plugin()

        assert plugin_factory_workflow.is_registered(PLUGIN_TEMPCAL_IMU)

    def test_plugin_can_be_created_after_registration(self) -> None:
        """
        Test registered plugin can be created through the factory.

        GIVEN: The tempcal_imu plugin is registered
        WHEN: Creating a plugin instance via the factory
        THEN: A valid TempCalIMUWorkflow instance should be returned
        """
        register_tempcal_imu_plugin()
        root_window = MagicMock()
        data_model = MagicMock()

        workflow = plugin_factory_workflow.create(PLUGIN_TEMPCAL_IMU, root_window, data_model)

        assert isinstance(workflow, TempCalIMUWorkflow)
        assert workflow.root_window is root_window
        assert workflow.data_model is data_model

    def test_unregistered_plugin_cannot_be_created(self) -> None:
        """
        Test unregistered plugin returns None when creation is attempted.

        GIVEN: The tempcal_imu plugin is NOT registered
        WHEN: Attempting to create the plugin via the factory
        THEN: None should be returned indicating plugin is unavailable
        """
        # Ensure plugin is not registered
        assert not plugin_factory_workflow.is_registered(PLUGIN_TEMPCAL_IMU)

        result = plugin_factory_workflow.create(PLUGIN_TEMPCAL_IMU, MagicMock(), MagicMock())

        assert result is None

    def test_factory_creates_new_instances_each_time(self) -> None:
        """
        Test factory creates fresh workflow instances for each request.

        GIVEN: A registered tempcal_imu plugin
        WHEN: Creating multiple workflow instances
        THEN: Each instance should be independent (not singleton pattern)
        """
        register_tempcal_imu_plugin()

        workflow1 = plugin_factory_workflow.create(PLUGIN_TEMPCAL_IMU, MagicMock(), MagicMock())
        workflow2 = plugin_factory_workflow.create(PLUGIN_TEMPCAL_IMU, MagicMock(), MagicMock())

        assert workflow1 is not workflow2
        assert isinstance(workflow1, TempCalIMUWorkflow)
        assert isinstance(workflow2, TempCalIMUWorkflow)
