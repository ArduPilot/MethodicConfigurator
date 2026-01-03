#!/usr/bin/env python3

"""
BDD-style tests for the plugin_factory.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, patch

from ardupilot_methodic_configurator.plugin_factory import PluginFactory, plugin_factory

# pylint: disable=protected-access


class TestPluginFactory:
    """Test plugin factory functionality for dependency injection."""

    def test_user_can_initialize_plugin_factory(self) -> None:
        """
        User can initialize a plugin factory with an empty registry.

        GIVEN: A user needs to create a plugin factory
        WHEN: The factory is instantiated
        THEN: It should have an empty creators registry
        """
        # Act: Create a new plugin factory
        factory = PluginFactory()

        # Assert: Factory is initialized with empty registry
        assert not factory._creators
        assert isinstance(factory._creators, dict)

    def test_user_can_register_plugin_creator_function(self) -> None:
        """
        User can register a plugin creator function with a unique name.

        GIVEN: A user has a plugin creator function
        WHEN: The creator function is registered with a unique name
        THEN: The factory should store the creator function for later use
        """
        # Arrange: Create factory and mock creator function
        factory = PluginFactory()
        mock_creator = MagicMock(return_value="mock_plugin_instance")

        # Act: Register the plugin creator
        factory.register("test_plugin", mock_creator)

        # Assert: Creator is stored in registry
        assert "test_plugin" in factory._creators
        assert factory._creators["test_plugin"] is mock_creator

    def test_user_can_register_plugin_that_overwrites_existing_registration(self) -> None:
        """
        User can register a plugin that overwrites an existing registration.

        GIVEN: A plugin name is already registered
        WHEN: A new creator function is registered with the same name
        THEN: The new creator should overwrite the old one
        AND: An error should be logged about the overwrite
        """
        # Arrange: Create factory with existing registration
        factory = PluginFactory()
        old_creator = MagicMock(return_value="old_plugin")
        new_creator = MagicMock(return_value="new_plugin")

        factory.register("test_plugin", old_creator)

        # Act: Register new creator with same name
        with patch("ardupilot_methodic_configurator.plugin_factory.logging_error") as mock_log:
            factory.register("test_plugin", new_creator)

            # Assert: Error is logged about overwrite
            mock_log.assert_called_once_with("Plugin '%s' is already registered, overwriting", "test_plugin")

        # Assert: New creator overwrote the old one
        assert factory._creators["test_plugin"] is new_creator

    def test_user_can_create_registered_plugin_instance(self) -> None:
        """
        User can create a plugin instance using a registered creator function.

        GIVEN: A plugin creator is registered
        WHEN: The factory is asked to create that plugin
        THEN: The creator function should be called with correct parameters
        AND: The created plugin instance should be returned
        """
        # Arrange: Create factory and register plugin
        factory = PluginFactory()
        mock_creator = MagicMock(return_value="created_plugin_instance")
        factory.register("test_plugin", mock_creator)

        # Mock parameters
        mock_parent = MagicMock()
        mock_model = MagicMock()
        mock_base_window = MagicMock()

        # Act: Create plugin instance
        result = factory.create("test_plugin", mock_parent, mock_model, mock_base_window)

        # Assert: Creator was called with correct parameters
        mock_creator.assert_called_once_with(mock_parent, mock_model, mock_base_window)

        # Assert: Created instance is returned
        assert result == "created_plugin_instance"

    def test_user_receives_none_when_creating_unregistered_plugin(self) -> None:
        """
        User receives None when attempting to create an unregistered plugin.

        GIVEN: A plugin name is not registered
        WHEN: The factory is asked to create that plugin
        THEN: None should be returned
        """
        # Arrange: Create factory without registering any plugins
        factory = PluginFactory()

        # Act: Attempt to create unregistered plugin
        result = factory.create("nonexistent_plugin", MagicMock(), MagicMock(), MagicMock())

        # Assert: None is returned
        assert result is None

    def test_user_can_check_if_plugin_is_registered(self) -> None:
        """
        User can check if a plugin is registered.

        GIVEN: A plugin factory with some registered plugins
        WHEN: The user checks registration status
        THEN: Correct boolean values should be returned
        """
        # Arrange: Create factory and register one plugin
        factory = PluginFactory()
        factory.register("registered_plugin", MagicMock())

        # Act & Assert: Check registration status
        assert factory.is_registered("registered_plugin") is True
        assert factory.is_registered("unregistered_plugin") is False

    def test_user_can_use_global_plugin_factory_instance(self) -> None:
        """
        User can use the global plugin factory instance.

        GIVEN: The global plugin_factory instance exists
        WHEN: The user accesses it
        THEN: It should be a properly initialized PluginFactory instance
        """
        # Assert: Global instance is available and properly initialized
        assert isinstance(plugin_factory, PluginFactory)
        assert hasattr(plugin_factory, "_creators")
        assert hasattr(plugin_factory, "register")
        assert hasattr(plugin_factory, "create")
        assert hasattr(plugin_factory, "is_registered")

    def test_user_can_register_different_plugin_types(self) -> None:
        """
        User can register different types of plugins with different signatures.

        GIVEN: Multiple plugin types with different creator signatures
        WHEN: They are registered
        THEN: All should be stored correctly
        """
        # Arrange: Create factory
        factory = PluginFactory()

        # Different creator functions
        motor_test_creator = MagicMock(return_value="motor_test_plugin")
        parameter_editor_creator = MagicMock(return_value="parameter_editor_plugin")

        # Act: Register different plugin types
        factory.register("motor_test", motor_test_creator)
        factory.register("parameter_editor", parameter_editor_creator)

        # Assert: Both are registered
        assert factory.is_registered("motor_test") is True
        assert factory.is_registered("parameter_editor") is True
        assert len(factory._creators) == 2

    def test_user_can_create_plugins_with_different_parent_types(self) -> None:
        """
        User can create plugins with different parent widget types.

        GIVEN: Plugins that accept different parent widget types (tk.Frame vs ttk.Frame)
        WHEN: They are created
        THEN: The correct parent type should be passed to each creator
        """
        # Arrange: Create factory and register plugins
        factory = PluginFactory()

        tk_creator = MagicMock(return_value="tk_plugin")
        ttk_creator = MagicMock(return_value="ttk_plugin")

        factory.register("tk_plugin", tk_creator)
        factory.register("ttk_plugin", ttk_creator)

        # Mock different parent types
        tk_parent = MagicMock(spec=["tk"])
        ttk_parent = MagicMock(spec=["ttk"])

        # Act: Create plugins with different parent types
        factory.create("tk_plugin", tk_parent, MagicMock(), MagicMock())
        factory.create("ttk_plugin", ttk_parent, MagicMock(), MagicMock())

        # Assert: Correct parent types were passed
        tk_creator.assert_called_once()
        ttk_creator.assert_called_once()

    def test_user_receives_none_when_creator_function_returns_none(self) -> None:
        """
        User receives None when the creator function itself returns None.

        GIVEN: A registered plugin creator that returns None
        WHEN: The plugin is created
        THEN: None should be returned (not an error)
        """
        # Arrange: Create factory with creator that returns None
        factory = PluginFactory()
        mock_creator = MagicMock(return_value=None)
        factory.register("none_plugin", mock_creator)

        # Act: Create plugin
        result = factory.create("none_plugin", MagicMock(), MagicMock(), MagicMock())

        # Assert: None is returned
        assert result is None
        # But creator was still called
        mock_creator.assert_called_once()

    def test_user_can_register_empty_string_plugin_name(self) -> None:
        """
        User can register a plugin with an empty string name.

        GIVEN: A plugin creator function
        WHEN: It is registered with an empty string name
        THEN: It should be stored and retrievable
        """
        # Arrange: Create factory
        factory = PluginFactory()
        mock_creator = MagicMock(return_value="empty_name_plugin")

        # Act: Register with empty name
        factory.register("", mock_creator)

        # Assert: Can be retrieved and created
        assert factory.is_registered("") is True
        result = factory.create("", MagicMock(), MagicMock(), MagicMock())
        assert result == "empty_name_plugin"

    def test_user_can_register_plugin_with_special_characters_in_name(self) -> None:
        """
        User can register plugins with special characters in names.

        GIVEN: Plugin names with special characters
        WHEN: They are registered
        THEN: They should work correctly
        """
        # Arrange: Create factory
        factory = PluginFactory()
        mock_creator = MagicMock(return_value="special_plugin")

        # Act: Register with special characters
        factory.register("plugin-with-dashes", mock_creator)
        factory.register("plugin_with_underscores", mock_creator)
        factory.register("plugin.123", mock_creator)

        # Assert: All can be registered and checked
        assert factory.is_registered("plugin-with-dashes") is True
        assert factory.is_registered("plugin_with_underscores") is True
        assert factory.is_registered("plugin.123") is True
