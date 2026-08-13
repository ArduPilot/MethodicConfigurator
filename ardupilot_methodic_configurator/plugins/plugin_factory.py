"""
Plugin factory for creating plugin instances without circular imports.

This factory implements the dependency injection pattern, allowing plugins
to self-register and be instantiated without the main application directly
importing plugin classes.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from logging import error as logging_error
from tkinter import ttk
from typing import TYPE_CHECKING

from ardupilot_methodic_configurator import _

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
    from ardupilot_methodic_configurator.backend_flightcontroller import FlightController
    from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor

# Note: PluginView is defined in plugin_protocol for documentation purposes
# Type alias for plugin creator functions
# Note: We use object types to allow plugin creators to be more specific with their types
PluginCreator = Callable[[tk.Frame | ttk.Frame, object, object], object]
PluginModelCreator = Callable[["PluginModelContext"], object]


@dataclass(frozen=True)
class PluginModelContext:
    """Dependencies available to a registered plugin data-model factory."""

    flight_controller: FlightController
    local_filesystem: LocalFilesystem
    parameter_editor: ParameterEditor


class PluginFactory:
    """
    Factory for creating plugin instances.

    Plugins register themselves with the factory using a unique name.
    The factory can then create plugin instances without the caller
    needing to know about or import the concrete plugin classes.
    """

    def __init__(self) -> None:
        """Initialize the plugin factory with an empty registry."""
        self._creators: dict[str, PluginCreator] = {}
        self._model_creators: dict[str, PluginModelCreator] = {}

    def register(
        self,
        plugin_name: str,
        creator_func: PluginCreator,
        model_creator_func: PluginModelCreator | None = None,
    ) -> None:
        """
        Register a plugin creator function.

        Args:
            plugin_name: Unique identifier for the plugin
            creator_func: Function that creates a plugin instance.
                         Should accept (parent, model, base_window) and return PluginView
            model_creator_func: Function that creates the plugin data model from shared dependencies

        """
        if plugin_name in self._creators:
            logging_error("Plugin '%s' is already registered, overwriting", plugin_name)
        self._creators[plugin_name] = creator_func
        if model_creator_func is not None:
            self._model_creators[plugin_name] = model_creator_func
        else:
            self._model_creators.pop(plugin_name, None)

    def create(
        self,
        plugin_name: str,
        parent: tk.Frame | ttk.Frame,
        model: object,
        base_window: object,
    ) -> object | None:
        """
        Create a plugin instance.

        Args:
            plugin_name: The name of the plugin to create
            parent: The parent frame for the plugin
            model: The data model for the plugin
            base_window: The base window instance

        Returns:
            The created plugin instance (should implement PluginView protocol), or None if plugin not found

        """
        creator = self._creators.get(plugin_name)
        if creator:
            return creator(parent, model, base_window)
        return None

    def create_model(self, plugin_name: str, context: PluginModelContext) -> object | None:
        """Create a registered plugin's data model, or return None if no model factory exists."""
        creator = self._model_creators.get(plugin_name)
        if creator is None:
            return None
        return creator(context)

    def is_registered(self, plugin_name: str) -> bool:
        """
        Check if a plugin is registered.

        Args:
            plugin_name: The name of the plugin to check

        Returns:
            True if the plugin is registered, False otherwise

        """
        return plugin_name in self._creators

    def available_plugins(self) -> list[str]:
        """Return the registered plugin names in sorted order."""
        return sorted(self._creators)

    def validate_configuration_steps(self, configuration_steps: dict[str, dict]) -> None:
        """
        Validate that all plugins referenced in configuration steps are registered.

        Called at application startup (see ``register_plugins()`` in ``__main__.py``)
        after all plugins have been registered.  Logs an error for every plugin name
        that appears in the configuration JSON but has no registered creator.

        Args:
            configuration_steps: Mapping of filename → step-info dict, as returned
                                  by ``LocalFilesystem.configuration_steps``.

        """
        configured_plugins: set[str] = set()
        for file_info in configuration_steps.values():
            plugin = file_info.get("plugin")
            if plugin and plugin.get("name"):
                configured_plugins.add(plugin["name"])

        available = ", ".join(self.available_plugins()) or _("none")
        for plugin_name in configured_plugins:
            if not self.is_registered(plugin_name):
                logging_error(
                    _("Plugin '%(plugin_name)s' is configured but not registered. Available plugins: %(available)s"),
                    {"plugin_name": plugin_name, "available": available},
                )


# Global factory instance
plugin_factory = PluginFactory()
