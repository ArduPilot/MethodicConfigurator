#!/usr/bin/env python3

"""
Tests for UI plugin factory.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.plugin_factory_ui import PluginFactoryUI


class TestPluginFactoryUI:
    """Test suite for UI plugin factory."""

    @pytest.fixture
    def factory(self) -> PluginFactoryUI:
        """Create a fresh factory instance for each test."""
        return PluginFactoryUI()

    @pytest.fixture
    def mock_creator(self) -> MagicMock:
        """
        Create a mock creator function.

        Returns a mock plugin view instance when called.
        """
        mock_plugin_view = MagicMock()
        mock_plugin_view.show.return_value = None
        return MagicMock(return_value=mock_plugin_view)

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
        THEN: Should raise ValueError with descriptive message
        """
        factory.register("test_plugin", mock_creator)

        with pytest.raises(ValueError, match="Plugin 'test_plugin' is already registered"):
            factory.register("test_plugin", mock_creator)

    def test_create_registered_plugin_with_all_parameters(self, factory, mock_creator) -> None:
        """
        Test creating a registered plugin with all required parameters.

        GIVEN: A factory with a registered plugin
        WHEN: Creating the plugin with parent frame, model, and base window
        THEN: Should call creator with correct parameters and return plugin instance
        """
        factory.register("test_plugin", mock_creator)
        parent_frame = MagicMock()
        data_model = MagicMock()
        base_window = MagicMock()

        result = factory.create("test_plugin", parent_frame, data_model, base_window)

        assert result is not None
        mock_creator.assert_called_once_with(parent_frame, data_model, base_window)

    def test_create_unregistered_plugin_returns_none(self, factory) -> None:
        """
        Test creating an unregistered plugin.

        GIVEN: A factory without a registered plugin
        WHEN: Attempting to create a nonexistent plugin
        THEN: Should return None gracefully
        """
        result = factory.create("nonexistent_plugin", MagicMock(), MagicMock(), MagicMock())

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
        WHEN: Getting the list of registered plugins
        THEN: Should return empty list
        """
        assert factory.get_registered_plugins() == []

    def test_get_registered_plugins_multiple(self, factory) -> None:
        """
        Test getting multiple registered plugins.

        GIVEN: A factory with multiple registered plugins
        WHEN: Getting the list of registered plugins
        THEN: Should return list containing all plugin names
        """
        factory.register("motor_test", MagicMock())
        factory.register("tempcal_imu", MagicMock())
        factory.register("compass_calibration", MagicMock())

        plugins = factory.get_registered_plugins()

        assert len(plugins) == 3
        assert "motor_test" in plugins
        assert "tempcal_imu" in plugins
        assert "compass_calibration" in plugins

    def test_plugin_creator_receives_correct_parent_frame_type(self, factory) -> None:
        """
        Test that plugin creator receives the correct parent frame.

        GIVEN: A factory with a registered plugin
        WHEN: Creating a plugin with a specific parent frame type
        THEN: The creator should receive the exact parent frame instance
        """
        mock_creator = MagicMock()
        factory.register("test_plugin", mock_creator)
        parent_frame = MagicMock()

        factory.create("test_plugin", parent_frame, MagicMock(), MagicMock())

        # Verify the exact parent frame instance was passed
        call_args = mock_creator.call_args[0]
        assert call_args[0] is parent_frame

    def test_multiple_plugins_can_coexist(self, factory) -> None:
        """
        Test multiple different plugins can be registered and created independently.

        GIVEN: A factory with multiple registered plugins
        WHEN: Creating different plugin instances
        THEN: Each should be created independently with their respective creators
        """
        creator1 = MagicMock(return_value="plugin1_instance")
        creator2 = MagicMock(return_value="plugin2_instance")

        factory.register("plugin1", creator1)
        factory.register("plugin2", creator2)

        result1 = factory.create("plugin1", MagicMock(), MagicMock(), MagicMock())
        result2 = factory.create("plugin2", MagicMock(), MagicMock(), MagicMock())

        assert result1 == "plugin1_instance"
        assert result2 == "plugin2_instance"
        creator1.assert_called_once()
        creator2.assert_called_once()
