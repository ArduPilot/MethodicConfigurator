"""
Protocol definitions for the plugin system.

This file defines the interface that all plugins must implement,
enabling dependency injection and avoiding circular imports.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from __future__ import annotations

from enum import Enum, auto
from functools import partial
from typing import TYPE_CHECKING, Protocol, cast

if TYPE_CHECKING:
    import tkinter as tk
    from collections.abc import Callable
    from tkinter import ttk


class PluginPauseReason(Enum):
    """Why another owner needs the shared FC connection."""

    EXCLUSIVE_OPERATION = auto()
    CONNECTION_RECOVERY = auto()


class SuspendablePlugin(Protocol):
    """Optional paired lifecycle for yielding reception without hiding a view."""

    def on_suspend(self, reason: PluginPauseReason = PluginPauseReason.EXCLUSIVE_OPERATION) -> None:
        """Yield reception; stop actuators for tools and avoid commands during recovery."""

    def on_resume(self) -> None:
        """Resume polling idempotently, retaining workflow state and discarding stale samples."""


class PluginView(Protocol):
    """
    Protocol that all plugin views must implement.

    This defines the interface contract for plugins without requiring
    concrete implementations to inherit from a base class.

    Resource Cleanup Contract:
        Plugins that allocate resources (timers, callbacks, network connections, etc.)
        MUST implement proper cleanup through the lifecycle methods:
        - on_activate(): Start timers and initialize active resources
        - on_deactivate(): Stop timers and release active resources
        - destroy(): Final cleanup of all resources when the plugin is removed

        This ensures plugins don't leak resources when hidden or removed.

    Temporary Diagnostics Pause:
        Views may implement SuspendablePlugin to preserve workflow state while
        yielding reception. PluginPauseReason distinguishes exclusive FC tools
        (stop actuators before blocking their controls) from passive connection
        checks and recovery (avoid sending commands). Both hooks are required.
        Other views use on_deactivate()/on_activate() for safety cleanup.
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
        """
        Clean up the plugin view and release all resources.

        This method is called when the plugin is being permanently removed.
        Implementations must:
        - Cancel any active timers (using after_cancel for tkinter timers)
        - Close any open connections or file handles
        - Unregister any callbacks or observers
        - Call parent class destroy() if inherited
        """

    def on_activate(self) -> None:
        """
        Called when the plugin becomes active (visible).

        This is called when the plugin is made visible.
        Implementations should:
        - Start periodic timers or refresh tasks
        - Initialize resources that should only be active when visible
        - Refresh display with current data
        - Re-establish connections if needed

        Example:
            self._timer_id = self.after(500, self._periodic_update)

        """

    def on_deactivate(self) -> None:
        """
        Called when the plugin becomes inactive (hidden).

        This is called when switching away from the plugin's view.
        Implementations must:
        - Cancel all active timers (critical for resource management)
        - Save any unsaved state
        - Close temporary resources
        - Stop refresh tasks

        Example:
            if self._timer_id:
                self.after_cancel(self._timer_id)
                self._timer_id = None

        """


def resolve_plugin_lifecycle(
    plugin: object, reason: PluginPauseReason
) -> tuple[Callable[[], None], Callable[[], None]] | None:
    """Prefer paired suspend/resume hooks, falling back to paired hide/show hooks."""
    if callable(getattr(plugin, "on_suspend", None)) and callable(getattr(plugin, "on_resume", None)):
        suspendable = cast("SuspendablePlugin", plugin)
        return partial(suspendable.on_suspend, reason), suspendable.on_resume
    if callable(getattr(plugin, "on_deactivate", None)) and callable(getattr(plugin, "on_activate", None)):
        view = cast("PluginView", plugin)
        return view.on_deactivate, view.on_activate
    return None
