"""
Protocol definitions for the plugin system.

This file defines the interface that all plugins must implement,
enabling dependency injection and avoiding circular imports.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import tkinter as tk
    from tkinter import ttk


class PluginView(Protocol):
    """
    Protocol that all plugin views must implement.

    This defines the interface contract for plugins without requiring
    concrete implementations to inherit from a base class.
    """

    def __init__(
        self,
        parent: tk.Frame | ttk.Frame,
        model: object,
        base_window: object,
    ) -> None:
        """
        Initialize the plugin view.

        Args:
            parent: The parent frame where the plugin will be displayed
            model: The data model for the plugin (plugin-specific type)
            base_window: The base window instance for accessing application services

        """

    def pack(self, *, fill: str = "none", expand: bool = False, **kwargs: str | bool | int) -> None:
        """
        Pack the plugin view into its parent frame.

        Args:
            fill: How to fill available space ('none', 'x', 'y', 'both')
            expand: Whether to expand to fill parent
            **kwargs: Additional packing options (side, padx, pady, etc.)

        """

    def destroy(self) -> None:
        """Clean up the plugin view and release resources."""

    def on_activate(self) -> None:
        """
        Called when the plugin becomes active (visible).

        Use this to start timers, refresh data, or initialize resources
        that should only be active when the plugin is visible.
        """

    def on_deactivate(self) -> None:
        """
        Called when the plugin becomes inactive (hidden).

        Use this to stop timers, release resources, or save state
        when switching away from this plugin.
        """
