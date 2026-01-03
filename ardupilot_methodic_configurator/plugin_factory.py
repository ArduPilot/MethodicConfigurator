"""
Plugin factory for creating plugin instances without circular imports.

This factory implements the dependency injection pattern, allowing plugins
to self-register and be instantiated without the main application directly
importing plugin classes.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from logging import error as logging_error
from tkinter import ttk
from typing import Callable, Optional, Union

# Note: PluginView is defined in plugin_protocol for documentation purposes
# Type alias for plugin creator functions
# Note: We use object types to allow plugin creators to be more specific with their types
PluginCreator = Callable[[Union[tk.Frame, ttk.Frame], object, object], object]


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

    def register(self, plugin_name: str, creator_func: PluginCreator) -> None:
        """
        Register a plugin creator function.

        Args:
            plugin_name: Unique identifier for the plugin
            creator_func: Function that creates a plugin instance.
                         Should accept (parent, model, base_window) and return PluginView

        """
        if plugin_name in self._creators:
            logging_error("Plugin '%s' is already registered, overwriting", plugin_name)
        self._creators[plugin_name] = creator_func

    def create(
        self,
        plugin_name: str,
        parent: Union[tk.Frame, ttk.Frame],
        model: object,
        base_window: object,
    ) -> Optional[object]:
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

    def is_registered(self, plugin_name: str) -> bool:
        """
        Check if a plugin is registered.

        Args:
            plugin_name: The name of the plugin to check

        Returns:
            True if the plugin is registered, False otherwise

        """
        return plugin_name in self._creators


# Global factory instance
plugin_factory = PluginFactory()
