#!/usr/bin/env python3

"""
Tests for workflow plugin factory.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.plugin_factory_workflow import PluginFactoryWorkflow


class TestPluginFactoryWorkflow:
    """Test suite for workflow plugin factory."""

    @pytest.fixture
    def factory(self) -> PluginFactoryWorkflow:
        """Create a fresh factory instance for each test."""
        return PluginFactoryWorkflow()

    @pytest.fixture
    def mock_creator(self) -> MagicMock:
        """Create a mock creator function."""
        return MagicMock(return_value="mock_workflow")

    def test_register_plugin(self, factory, mock_creator) -> None:
        """
        Test registering a plugin.

        GIVEN: A factory and a creator function
        WHEN: Registering a plugin
        THEN: Plugin should be registered successfully
        """
        factory.register("test_plugin", mock_creator)

        assert factory.is_registered("test_plugin")
        assert "test_plugin" in factory.get_registered_plugins()

    def test_register_duplicate_plugin_raises_error(self, factory, mock_creator) -> None:
        """
        Test registering duplicate plugin raises ValueError.

        GIVEN: A factory with an already registered plugin
        WHEN: Attempting to register the same plugin again
        THEN: Should raise ValueError
        """
        factory.register("test_plugin", mock_creator)

        with pytest.raises(ValueError, match="Workflow plugin 'test_plugin' is already registered"):
            factory.register("test_plugin", mock_creator)

    def test_create_registered_plugin(self, factory, mock_creator) -> None:
        """
        Test creating a registered plugin.

        GIVEN: A factory with a registered plugin
        WHEN: Creating the plugin
        THEN: Should call creator and return result
        """
        factory.register("test_plugin", mock_creator)
        root_window = MagicMock()
        data_model = MagicMock()

        result = factory.create("test_plugin", root_window, data_model)

        assert result == "mock_workflow"
        mock_creator.assert_called_once_with(root_window, data_model)

    def test_create_unregistered_plugin_returns_none(self, factory) -> None:
        """
        Test creating an unregistered plugin.

        GIVEN: A factory without a registered plugin
        WHEN: Attempting to create the plugin
        THEN: Should return None
        """
        result = factory.create("nonexistent_plugin", MagicMock(), MagicMock())

        assert result is None

    def test_is_registered_for_nonexistent_plugin(self, factory) -> None:
        """
        Test checking if nonexistent plugin is registered.

        GIVEN: A factory without a registered plugin
        WHEN: Checking if plugin is registered
        THEN: Should return False
        """
        assert not factory.is_registered("nonexistent_plugin")

    def test_get_registered_plugins_empty(self, factory) -> None:
        """
        Test getting registered plugins when none exist.

        GIVEN: A factory with no registered plugins
        WHEN: Getting registered plugins
        THEN: Should return empty list
        """
        assert factory.get_registered_plugins() == []

    def test_get_registered_plugins_multiple(self, factory) -> None:
        """
        Test getting multiple registered plugins.

        GIVEN: A factory with multiple registered plugins
        WHEN: Getting registered plugins
        THEN: Should return list of all plugin names
        """
        factory.register("plugin1", MagicMock())
        factory.register("plugin2", MagicMock())
        factory.register("plugin3", MagicMock())

        plugins = factory.get_registered_plugins()

        assert len(plugins) == 3
        assert "plugin1" in plugins
        assert "plugin2" in plugins
        assert "plugin3" in plugins
