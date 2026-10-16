#!/usr/bin/env python3

"""
BDD-style tests for the plugin_factory.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from types import MethodType, SimpleNamespace
from typing import get_type_hints
from unittest.mock import MagicMock, patch

import pytest
from pytest_mock import MockerFixture

from ardupilot_methodic_configurator.__main__ import register_plugins
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow
from ardupilot_methodic_configurator.plugins import plugin_constants
from ardupilot_methodic_configurator.plugins.plugin_factory import PluginFactory, PluginModelContext, plugin_factory
from ardupilot_methodic_configurator.plugins.plugin_protocol import PluginPauseReason

# pylint: disable=protected-access


class TestPluginFactory:
    """Test plugin factory functionality for dependency injection."""

    def test_every_registered_view_declares_a_connection_recovery_lifecycle(self, mocker: MockerFixture) -> None:
        """
        Every plugin declares a lifecycle that lets the editor recover its connection.

        This is an interface check; real polling views separately exercise timer and receiver cleanup.

        GIVEN: All plugins are registered through the application's startup path
        WHEN: The editor pauses each view through its connection recovery entry point
        THEN: Recovery receives a callable that resumes the same view exactly once
        """
        for registry in (
            plugin_factory._creators,
            plugin_factory._model_creators,
            plugin_factory._flight_controller_requirements,
        ):
            mocker.patch.dict(registry, clear=True)
        register_plugins()
        expected = {
            value for name, value in vars(plugin_constants).items() if name.startswith("PLUGIN_") and isinstance(value, str)
        }
        assert set(plugin_factory.available_plugins()) == expected

        for name in plugin_factory.available_plugins():
            # Enforce the real registered view's method surface without constructing its UI.
            view_type = get_type_hints(plugin_factory._creators[name])["return"]
            view = MagicMock(spec_set=view_type)
            editor = SimpleNamespace(current_plugin_view=view, root=MagicMock())
            editor._pause_plugin_receiver = MethodType(ParameterEditorWindow._pause_plugin_receiver, editor)

            resume = ParameterEditorWindow._pause_connection_plugin(editor)

            assert callable(resume), f"{name} blocks connection recovery"
            resume()
            resume()
            if callable(getattr(view, "on_suspend", None)) and callable(getattr(view, "on_resume", None)):
                view.on_suspend.assert_called_once_with(PluginPauseReason.CONNECTION_RECOVERY)
                view.on_resume.assert_called_once_with()
            else:
                view.on_deactivate.assert_called_once_with()
                view.on_activate.assert_called_once_with()

    def test_user_is_told_once_about_each_unavailable_configured_plugin(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        Identify unavailable plugins and suggest registered alternatives.

        GIVEN: Configuration steps reference a registered plugin and repeated unavailable plugins
        WHEN: Startup validates the configuration
        THEN: Each unavailable name is logged once with the sorted available names
        """
        # Given: A real registry and realistic configuration-step metadata.
        factory = PluginFactory()
        factory.register("zeta", lambda _parent, _model, _window: object())
        factory.register("alpha", lambda _parent, _model, _window: object())
        steps: dict[str, dict[str, object]] = {
            "01.param": {"plugin": {"name": "missing"}},
            "02.param": {"plugin": {"name": "missing"}},
            "03.param": {"plugin": {"name": "another"}},
            "04.param": {"plugin": {"name": "alpha"}},
            "05.param": {},
            "06.param": {"plugin": {}},
            "07.param": {"plugin": {"name": ""}},
        }

        # When: Validate all references.
        factory.validate_configuration_steps(steps)

        # Then: Repeated references produce one actionable error per missing name.
        assert sorted(caplog.messages) == [
            "Plugin 'another' is configured but not registered. Available plugins: alpha, zeta",
            "Plugin 'missing' is configured but not registered. Available plugins: alpha, zeta",
        ]
        assert all(record.levelname == "ERROR" for record in caplog.records)

    def test_user_is_told_when_no_plugins_are_available(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        Diagnose a configured plugin when the registry is empty.

        GIVEN: No plugins are registered
        WHEN: A configuration step references a plugin
        THEN: The diagnostic explicitly says that no plugins are available
        """
        # Given: An empty registry.
        factory = PluginFactory()

        # When: Validate an unavailable plugin reference.
        factory.validate_configuration_steps({"01.param": {"plugin": {"name": "motor_test"}}})

        # Then: The user gets a useful empty-registry diagnostic.
        assert caplog.messages == ["Plugin 'motor_test' is configured but not registered. Available plugins: none"]

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
        assert not factory._model_creators
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
        with patch("ardupilot_methodic_configurator.plugins.plugin_factory.logging_error") as mock_log:
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

    def test_registered_model_factory_receives_shared_dependency_context(self) -> None:
        factory = PluginFactory()
        model_creator = MagicMock(return_value="created_model")
        context = PluginModelContext(MagicMock(), MagicMock(), MagicMock())
        factory.register("test_plugin", MagicMock(), model_creator)

        result = factory.create_model("test_plugin", context)

        assert result == "created_model"
        model_creator.assert_called_once_with(context)

    def test_plugins_require_a_flight_controller_by_default_but_can_opt_out(self) -> None:
        """Existing hardware-backed plugins stay gated while offline plugins can opt out."""
        factory = PluginFactory()
        factory.register("hardware_plugin", MagicMock())
        factory.register("offline_plugin", MagicMock(), requires_flight_controller=False)

        assert factory.requires_flight_controller("hardware_plugin") is True
        assert factory.requires_flight_controller("offline_plugin") is False
        assert factory.requires_flight_controller("unknown_plugin") is True

    def test_unregistered_model_factory_returns_none(self) -> None:
        factory = PluginFactory()

        assert factory.create_model("unknown", PluginModelContext(MagicMock(), MagicMock(), MagicMock())) is None

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
        assert hasattr(plugin_factory, "create_model")
        assert hasattr(plugin_factory, "is_registered")
        assert hasattr(plugin_factory, "available_plugins")

    def test_user_can_list_registered_plugins_in_sorted_order(self) -> None:
        """
        User can inspect the registered plugin names in alphabetical order.

        GIVEN: A plugin factory with multiple registrations
        WHEN: The user requests the list of available plugins
        THEN: The plugin names are returned sorted
        """
        factory = PluginFactory()
        factory.register("zeta", MagicMock())
        factory.register("alpha", MagicMock())
        factory.register("middle", MagicMock())

        assert factory.available_plugins() == ["alpha", "middle", "zeta"]

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


@pytest.mark.parametrize("steps", [{}, {"01.param": {}}, {"01.param": {"plugin": {"name": "available"}}}])
def test_valid_configuration_does_not_report_unavailable_plugins(
    caplog: pytest.LogCaptureFixture, steps: dict[str, dict[str, object]]
) -> None:
    """
    Accept steps without plugins and steps with registered plugins.

    GIVEN: Only available plugins or no plugin references
    WHEN: Startup validates configuration steps
    THEN: No plugin availability errors are logged
    """
    # Given: A registry containing every referenced plugin.
    factory = PluginFactory()
    factory.register("available", lambda _parent, _model, _window: object())

    # When: Validate configuration.
    factory.validate_configuration_steps(steps)

    # Then: Startup diagnostics remain clear.
    assert not caplog.records
