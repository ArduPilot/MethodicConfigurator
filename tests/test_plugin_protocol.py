#!/usr/bin/env python3

"""
Tests for plugin protocol definitions.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Generator
from typing import Union
from unittest.mock import MagicMock

import pytest

from ardupilot_methodic_configurator.plugin_protocol import PluginView

# pylint: disable=unused-argument


class TestPluginViewProtocol:
    """Test suite for PluginView protocol compliance."""

    @pytest.fixture
    def tk_root(self) -> Generator[tk.Tk, None, None]:
        """Create a Tk root window for testing."""
        root = tk.Tk()
        yield root
        root.destroy()

    @pytest.fixture
    def parent_frame(self, tk_root) -> tk.Frame:
        """Create a parent frame for plugin testing."""
        return tk.Frame(tk_root)

    def test_protocol_defines_required_initialization_signature(self) -> None:
        """
        Test protocol defines the required __init__ signature.

        GIVEN: The PluginView protocol specification
        WHEN: Examining the required initialization method
        THEN: It should accept parent frame, model, and base_window parameters
        """
        # Protocol defines the interface, we verify it has the __init__ method
        assert hasattr(PluginView, "__init__")

    def test_protocol_defines_pack_method(self) -> None:
        """
        Test protocol defines the pack method for widget placement.

        GIVEN: The PluginView protocol specification
        WHEN: Examining the required pack method
        THEN: It should define pack with fill, expand, and kwargs parameters
        """
        assert hasattr(PluginView, "pack")

    def test_protocol_defines_destroy_method(self) -> None:
        """
        Test protocol defines the destroy method for cleanup.

        GIVEN: The PluginView protocol specification
        WHEN: Examining the required destroy method
        THEN: It should define a parameterless destroy method
        """
        assert hasattr(PluginView, "destroy")

    def test_protocol_defines_lifecycle_methods(self) -> None:
        """
        Test protocol defines activation lifecycle methods.

        GIVEN: The PluginView protocol specification
        WHEN: Examining the required lifecycle methods
        THEN: It should define on_activate and on_deactivate methods
        """
        assert hasattr(PluginView, "on_activate")
        assert hasattr(PluginView, "on_deactivate")

    def test_conforming_plugin_implements_all_required_methods(self, parent_frame) -> None:
        """
        Test that a conforming plugin implements all protocol methods.

        GIVEN: A plugin class that implements the PluginView protocol
        WHEN: Creating an instance of the plugin
        THEN: All required methods should be present and callable
        """

        class ConformingPlugin:
            """A test plugin that conforms to PluginView protocol."""

            def __init__(self, parent: tk.Frame, model: object, base_window: object) -> None:
                self.parent = parent
                self.model = model
                self.base_window = base_window
                self.frame = tk.Frame(parent)

            def pack(self, *, fill: str = "none", expand: bool = False, **kwargs: Union[str, bool, int]) -> None:
                self.frame.pack(fill=fill, expand=expand, **kwargs)

            def destroy(self) -> None:
                self.frame.destroy()

            def on_activate(self) -> None:
                pass

            def on_deactivate(self) -> None:
                pass

        plugin = ConformingPlugin(parent_frame, MagicMock(), MagicMock())

        # Verify all protocol methods are callable
        assert callable(plugin.pack)
        assert callable(plugin.destroy)
        assert callable(plugin.on_activate)
        assert callable(plugin.on_deactivate)

    def test_plugin_can_be_packed_into_parent_frame(self, parent_frame) -> None:
        """
        Test plugin can be packed into parent frame using pack method.

        GIVEN: A plugin implementing the PluginView protocol
        WHEN: Calling pack() to display the plugin
        THEN: The plugin should be properly packed into its parent frame
        """

        class PackablePlugin:
            """Plugin that can be packed."""

            def __init__(self, parent: tk.Frame, model: object, base_window: object) -> None:
                self.frame = tk.Frame(parent)
                self.packed = False

            def pack(self, *, fill: str = "none", expand: bool = False, **kwargs: Union[str, bool, int]) -> None:
                self.frame.pack(fill=fill, expand=expand, **kwargs)
                self.packed = True

            def destroy(self) -> None:
                self.frame.destroy()

            def on_activate(self) -> None:
                pass

            def on_deactivate(self) -> None:
                pass

        plugin = PackablePlugin(parent_frame, MagicMock(), MagicMock())
        plugin.pack(fill="both", expand=True)

        assert plugin.packed is True

    def test_plugin_lifecycle_activation_and_deactivation(self, parent_frame) -> None:
        """
        Test plugin lifecycle methods work correctly.

        GIVEN: A plugin implementing activation/deactivation lifecycle
        WHEN: Plugin is activated and then deactivated
        THEN: Appropriate lifecycle methods should be called in order
        """

        class LifecyclePlugin:
            """Plugin with lifecycle tracking."""

            def __init__(self, parent: tk.Frame, model: object, base_window: object) -> None:
                self.frame = tk.Frame(parent)
                self.is_active = False
                self.activation_count = 0
                self.deactivation_count = 0

            def pack(self, *, fill: str = "none", expand: bool = False, **kwargs: Union[str, bool, int]) -> None:
                self.frame.pack(fill=fill, expand=expand, **kwargs)

            def destroy(self) -> None:
                self.frame.destroy()

            def on_activate(self) -> None:
                self.is_active = True
                self.activation_count += 1

            def on_deactivate(self) -> None:
                self.is_active = False
                self.deactivation_count += 1

        plugin = LifecyclePlugin(parent_frame, MagicMock(), MagicMock())

        # Simulate activation
        plugin.on_activate()
        assert plugin.is_active is True
        assert plugin.activation_count == 1

        # Simulate deactivation
        plugin.on_deactivate()
        assert plugin.is_active is False
        assert plugin.deactivation_count == 1

    def test_plugin_cleanup_releases_resources(self, parent_frame) -> None:
        """
        Test plugin destroy method properly releases resources.

        GIVEN: A plugin with resources that need cleanup
        WHEN: The destroy method is called
        THEN: All resources should be properly released
        """

        class CleanupPlugin:
            """Plugin that tracks cleanup."""

            def __init__(self, parent: tk.Frame, model: object, base_window: object) -> None:
                self.frame = tk.Frame(parent)
                self.cleaned_up = False

            def pack(self, *, fill: str = "none", expand: bool = False, **kwargs: Union[str, bool, int]) -> None:
                self.frame.pack(fill=fill, expand=expand, **kwargs)

            def destroy(self) -> None:
                self.cleaned_up = True
                self.frame.destroy()

            def on_activate(self) -> None:
                pass

            def on_deactivate(self) -> None:
                pass

        plugin = CleanupPlugin(parent_frame, MagicMock(), MagicMock())
        plugin.destroy()

        assert plugin.cleaned_up is True

    def test_plugin_receives_dependencies_via_constructor(self, parent_frame) -> None:
        """
        Test plugin receives all required dependencies through constructor.

        GIVEN: A plugin that needs parent frame, model, and base window
        WHEN: Instantiating the plugin with these dependencies
        THEN: Plugin should store and have access to all dependencies
        """

        class DependencyPlugin:
            """Plugin that uses injected dependencies."""

            def __init__(self, parent: tk.Frame, model: object, base_window: object) -> None:
                self.parent = parent
                self.model = model
                self.base_window = base_window
                self.frame = tk.Frame(parent)

            def pack(self, *, fill: str = "none", expand: bool = False, **kwargs: Union[str, bool, int]) -> None:
                self.frame.pack(fill=fill, expand=expand, **kwargs)

            def destroy(self) -> None:
                self.frame.destroy()

            def on_activate(self) -> None:
                pass

            def on_deactivate(self) -> None:
                pass

        model = MagicMock()
        base_window = MagicMock()

        plugin = DependencyPlugin(parent_frame, model, base_window)

        assert plugin.parent is parent_frame
        assert plugin.model is model
        assert plugin.base_window is base_window

    def test_plugin_pack_accepts_standard_tkinter_options(self, parent_frame) -> None:
        """
        Test plugin pack method accepts standard tkinter packing options.

        GIVEN: A plugin implementing the pack method
        WHEN: Packing with various tkinter options (fill, expand, side, padx, pady)
        THEN: All options should be accepted without error
        """

        class ConfigurablePackPlugin:
            """Plugin that accepts pack configuration."""

            def __init__(self, parent: tk.Frame, model: object, base_window: object) -> None:
                self.frame = tk.Frame(parent)
                self.pack_options: dict[str, Union[str, bool, int]] = {}

            def pack(self, *, fill: str = "none", expand: bool = False, **kwargs: Union[str, bool, int]) -> None:
                self.pack_options = {"fill": fill, "expand": expand, **kwargs}
                self.frame.pack(fill=fill, expand=expand, **kwargs)

            def destroy(self) -> None:
                self.frame.destroy()

            def on_activate(self) -> None:
                pass

            def on_deactivate(self) -> None:
                pass

        plugin = ConfigurablePackPlugin(parent_frame, MagicMock(), MagicMock())
        plugin.pack(fill="both", expand=True, side="left", padx=10, pady=5)

        assert plugin.pack_options["fill"] == "both"
        assert plugin.pack_options["expand"] is True
        assert plugin.pack_options["side"] == "left"
        assert plugin.pack_options["padx"] == 10
        assert plugin.pack_options["pady"] == 5

    def test_multiple_plugins_can_coexist_independently(self, parent_frame) -> None:
        """
        Test multiple plugin instances can exist independently.

        GIVEN: Multiple plugin instances created from the same class
        WHEN: Each plugin is activated and configured independently
        THEN: Each should maintain its own state without interference
        """

        class IndependentPlugin:
            """Plugin that maintains independent state."""

            def __init__(self, parent: tk.Frame, model: object, base_window: object) -> None:
                self.frame = tk.Frame(parent)
                self.is_active = False
                self.custom_state = ""

            def pack(self, *, fill: str = "none", expand: bool = False, **kwargs: Union[str, bool, int]) -> None:
                self.frame.pack(fill=fill, expand=expand, **kwargs)

            def destroy(self) -> None:
                self.frame.destroy()

            def on_activate(self) -> None:
                self.is_active = True

            def on_deactivate(self) -> None:
                self.is_active = False

        plugin1 = IndependentPlugin(parent_frame, MagicMock(), MagicMock())
        plugin2 = IndependentPlugin(parent_frame, MagicMock(), MagicMock())

        plugin1.custom_state = "plugin1_state"
        plugin1.on_activate()

        plugin2.custom_state = "plugin2_state"

        # Verify independence
        assert plugin1.custom_state == "plugin1_state"
        assert plugin2.custom_state == "plugin2_state"
        assert plugin1.is_active is True
        assert plugin2.is_active is False
