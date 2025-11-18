#!/usr/bin/env python3

"""
GUI tests for the ParameterEditorWindow using PyAutoGUI.

This module contains automated GUI tests for the Tkinter-based parameter editor.
Tests verify that the GUI initializes correctly and displays expected elements.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.configuration_manager import ConfigurationManager
from ardupilot_methodic_configurator.frontend_tkinter_about_popup_window import show_about_window
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import ParameterEditorWindow


class TestParameterEditorWindow:
    """Test cases for ParameterEditorWindow GUI initialization."""

    def test_pyautogui_setup(self, gui_test_environment) -> None:
        """Test that PyAutoGUI is properly configured for testing."""
        # The gui_test_environment fixture handles all the assertions

    @pytest.mark.skip(reason="Test blocks during execution - needs further investigation")
    def test_basic_gui_creation(self, test_config_manager: ConfigurationManager) -> None:
        """Test basic GUI creation without running mainloop."""
        # Create window but intercept mainloop
        window = None

        def mock_mainloop(self) -> None:
            """Mock mainloop to prevent blocking."""

        # Note: With the refactored code, mainloop is now in window.run()
        # so we don't need to patch it if we simply don't call run()
        # But we'll keep the patch for backwards compatibility
        try:
            # Patch mainloop to prevent blocking (though we won't call window.run())
            with (
                patch.object(tk.Tk, "mainloop", mock_mainloop),
                patch.object(ParameterEditorWindow, "put_image_in_label", return_value=MagicMock()),
            ):
                # Create the window (this no longer calls mainloop automatically)
                window = ParameterEditorWindow(test_config_manager)

            # Basic checks
            assert window.root is not None
            assert hasattr(window, "configuration_manager")
            assert window.configuration_manager is test_config_manager

            # Don't call window.run() in tests to avoid blocking

        finally:
            # Clean up window
            if window and window.root:
                window.root.destroy()

    @pytest.mark.skip(reason="GUI test requires display - run manually in GUI environment")
    def test_full_gui_with_pyautogui(self, test_config_manager: ConfigurationManager) -> None:  # pylint: disable=unused-argument
        """Full GUI test with PyAutoGUI - requires display."""
        # This test would run the full GUI and use PyAutoGUI to interact with it
        # For now, it's skipped as it requires a display environment

        # Example of what the test could do:
        # 1. Start GUI in separate thread
        # 2. Use PyAutoGUI to locate window
        # 3. Take screenshots
        # 4. Simulate mouse/keyboard interactions
        # 5. Verify GUI behavior

        pytest.skip("Full GUI test requires display environment")

    def test_display_usage_popup_window(self, mocker) -> None:
        """Test that the usage popup window can be created."""
        # Create a mock parent window
        parent = tk.Tk()
        parent.withdraw()  # Hide the parent window

        try:
            # Mock the UsagePopupWindow.display method to avoid actually showing the window
            mock_display = mocker.patch(
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.UsagePopupWindow.display"
            )

            # Call the method
            ParameterEditorWindow._display_usage_popup_window(parent)  # pylint: disable=protected-access

            # Verify that UsagePopupWindow.display was called
            mock_display.assert_called_once()
            args = mock_display.call_args[0]

            # Check that the correct arguments were passed
            assert len(args) >= 5  # parent, window, title, key, size
            assert "How to use the parameter file editor and uploader window" in args[2]  # title
            assert args[3] == "parameter_editor"  # key
            assert args[4] == "690x360"  # size

        finally:
            parent.destroy()

    def test_show_about_window(self, mocker) -> None:  # pylint: disable=too-many-locals
        """Test that the about window can be created."""
        # Create a mock root window
        root = tk.Tk()
        root.withdraw()  # Hide the root window

        try:
            # Mock webbrowser.open to avoid actually opening URLs
            mocker.patch("ardupilot_methodic_configurator.frontend_tkinter_about_popup_window.webbrowser_open")

            # Call the function
            show_about_window(root, "1.0.0")  # type: ignore[arg-type]

            # Find the about window (it should be a Toplevel child of root)
            about_windows = [child for child in root.winfo_children() if isinstance(child, tk.Toplevel)]

            # There should be exactly one about window
            assert len(about_windows) == 1
            about_window = about_windows[0]

            # Check window properties
            assert about_window.title() == "About"
            # Check that geometry contains the expected size (position may vary)
            geometry = about_window.geometry()
            assert "650x340" in geometry

            # Check that the window contains the expected content
            # Find all labels in the window (using ttk.Label)
            def find_labels(widget) -> list:
                labels = []
                # Check for both tk.Label and ttk.Label
                if isinstance(widget, (tk.Label, ttk.Label)):
                    labels.append(widget)
                for child in widget.winfo_children():
                    labels.extend(find_labels(child))
                return labels

            labels = find_labels(about_window)
            assert len(labels) > 0

            # Check that at least one label contains version information
            version_found = False
            for label in labels:
                text = label.cget("text")
                if "ArduPilot Methodic Configurator Version: 1.0.0" in text:
                    version_found = True
                    break
            assert version_found, "Version information not found in about window"

            # Check that buttons are created
            def find_buttons(widget) -> list:
                buttons = []
                # Check for both tk.Button and ttk.Button
                if isinstance(widget, (tk.Button, ttk.Button)):
                    buttons.append(widget)
                for child in widget.winfo_children():
                    buttons.extend(find_buttons(child))
                return buttons

            buttons = find_buttons(about_window)
            expected_buttons = ["User Manual", "Support Forum", "Report a Bug", "Licenses", "Source Code"]
            button_texts = [btn.cget("text") for btn in buttons]

            for expected_text in expected_buttons:
                assert expected_text in button_texts, f"Button '{expected_text}' not found"

            # Clean up the about window
            about_window.destroy()

        finally:
            root.destroy()

    def test_parameter_editor_window_initialization_attributes(self, test_config_manager: ConfigurationManager) -> None:
        """Test that ParameterEditorWindow can be instantiated with proper attributes."""
        with (
            patch.object(ParameterEditorWindow, "_create_conf_widgets"),
            patch.object(ParameterEditorWindow, "_create_documentation_widgets"),
            patch.object(ParameterEditorWindow, "_create_parameter_table_and_button_widgets"),
            patch.object(ParameterEditorWindow, "_update_widget_states"),
            patch("tkinter.Tk") as mock_tk,
        ):
            mock_root = MagicMock()
            mock_tk.return_value = mock_root

            window = ParameterEditorWindow(test_config_manager)

            # Verify basic attributes are set
            assert window.configuration_manager is test_config_manager
            assert hasattr(window, "gui_complexity")
            assert hasattr(window, "current_plugin")
            assert hasattr(window, "current_plugin_view")
            assert hasattr(window, "parameter_area_paned")

    def test_window_title_and_geometry_setup(self, test_config_manager: ConfigurationManager) -> None:
        """Test that window title and geometry are configured correctly."""
        with (
            patch.object(ParameterEditorWindow, "_create_conf_widgets"),
            patch.object(ParameterEditorWindow, "_create_documentation_widgets"),
            patch.object(ParameterEditorWindow, "_create_parameter_table_and_button_widgets"),
            patch.object(ParameterEditorWindow, "_update_widget_states"),
            patch("tkinter.Tk") as mock_tk,
        ):
            mock_root = MagicMock()
            mock_tk.return_value = mock_root

            ParameterEditorWindow(test_config_manager)

            # Verify window setup calls
            mock_root.title.assert_called()
            mock_root.geometry.assert_called_with("990x630")
            mock_root.protocol.assert_called()
