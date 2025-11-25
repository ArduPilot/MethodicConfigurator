#!/usr/bin/env python3

"""
Workflow plugin factory for managing workflow-based plugins.

Workflow plugins are triggered actions that execute when specific parameter files
are selected, rather than persistent UI components. They handle one-time operations
like calibration workflows, file uploads, or batch operations.

This factory implements a pattern symmetric to the UI plugin factory, properly
separating business logic (data models) from UI logic (workflow coordinators).

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from typing import Callable

# Type alias for workflow creator functions
# Workflow creators accept (root_window, data_model) and return a workflow coordinator object
WorkflowCreator = Callable[[object, object], object]


class PluginFactoryWorkflow:
    """
    Factory for creating workflow plugin coordinators.

    Workflow plugins differ from UI plugins in their lifecycle:
    - UI plugins: Create persistent views that remain visible
    - Workflow plugins: Create one-time coordinators that execute and complete

    However, both follow the same architectural pattern:
    1. Business logic is in a data model (e.g., TempCalIMUDataModel)
    2. UI coordination is in a coordinator/view (e.g., TempCalIMUWorkflow)
    3. Creation uses dependency injection via factory registration

    The factory maps plugin names to creator functions that instantiate
    workflow coordinators when triggered by parameter file selection.
    """

    def __init__(self) -> None:
        """Initialize the workflow plugin factory with an empty registry."""
        self._creators: dict[str, WorkflowCreator] = {}

    def register(self, plugin_name: str, creator_func: WorkflowCreator) -> None:
        """
        Register a workflow plugin creator function.

        Args:
            plugin_name: Unique identifier for the plugin (e.g., "tempcal_imu")
            creator_func: Function that creates a workflow coordinator instance.
                         Should accept (root_window, data_model) and return a workflow
                         coordinator object with a run_workflow() method.

        Raises:
            ValueError: If a plugin with the same name is already registered

        """
        if plugin_name in self._creators:
            msg = f"Workflow plugin '{plugin_name}' is already registered"
            raise ValueError(msg)
        self._creators[plugin_name] = creator_func

    def create(
        self,
        plugin_name: str,
        root_window: object,
        data_model: object,
    ) -> object | None:
        """
        Create a workflow coordinator instance.

        Args:
            plugin_name: The name of the workflow plugin to create
            root_window: The root window for creating dialogs
            data_model: The business logic data model for the workflow

        Returns:
            The created workflow coordinator instance, or None if plugin not found

        """
        creator = self._creators.get(plugin_name)
        if creator:
            return creator(root_window, data_model)
        return None

    def is_registered(self, plugin_name: str) -> bool:
        """
        Check if a workflow plugin is registered.

        Args:
            plugin_name: The plugin name to check

        Returns:
            bool: True if the plugin is registered, False otherwise

        """
        return plugin_name in self._creators

    def get_registered_plugins(self) -> list[str]:
        """
        Get list of all registered workflow plugin names.

        Returns:
            list[str]: List of registered plugin names

        """
        return list(self._creators.keys())


# Global workflow plugin factory instance
plugin_factory_workflow = PluginFactoryWorkflow()
