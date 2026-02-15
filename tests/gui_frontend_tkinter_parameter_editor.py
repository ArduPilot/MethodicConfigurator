#!/usr/bin/env python3

"""
GUI tests for the ParameterEditorWindow using PyAutoGUI.

This module contains automated GUI tests for the Tkinter-based parameter editor.
Tests verify that the GUI initializes correctly and displays expected elements.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from typing import cast
from unittest.mock import MagicMock, patch

import pyautogui
import pytest

from ardupilot_methodic_configurator.data_model_parameter_editor import ParameterEditor
from ardupilot_methodic_configurator.frontend_tkinter_about_popup_window import show_about_window
from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor import (
    ParameterEditorUiServices,
    ParameterEditorWindow,
)


class TestParameterEditorWindow:
    """Test cases for ParameterEditorWindow GUI initialization."""

    def test_pyautogui_setup(self, gui_test_environment) -> None:
        """Test that PyAutoGUI is properly configured for testing."""
        # The gui_test_environment fixture handles all the assertions

    @pytest.mark.skip(reason="Test blocks during execution - needs further investigation")
    def test_basic_gui_creation(self, test_param_editor: ParameterEditor) -> None:
        """Test basic GUI creation without running mainloop."""
        # Create window but intercept mainloop
        window = None

        def mock_mainloop(self) -> None:  # pylint: disable=unused-argument
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
                window = ParameterEditorWindow(test_param_editor)

            # Basic checks
            assert window.root is not None
            assert hasattr(window, "parameter_editor")
            assert window.parameter_editor is test_param_editor

            # Don't call window.run() in tests to avoid blocking

        finally:
            # Clean up window
            if window and window.root:
                window.root.destroy()

    def test_full_gui_with_pyautogui(self, gui_test_environment, mocker) -> None:  # pylint: disable=unused-argument
        """
        User can interact with GUI windows visible on screen using PyAutoGUI.

        GIVEN: A display environment is available for GUI testing
        WHEN: The about window is opened as a real Tkinter window
        THEN: PyAutoGUI can capture the screen and verify window presence
        AND: The window geometry is within screen bounds
        AND: The window is visible and interactable
        """
        # Arrange: Create a root window and the about dialog
        root = tk.Tk()
        root.withdraw()

        try:
            # Mock webbrowser to prevent URL opens
            mocker.patch("ardupilot_methodic_configurator.frontend_tkinter_about_popup_window.webbrowser_open_url")

            # Act: Open the about window
            show_about_window(root, "1.0.0")  # type: ignore[arg-type]

            # Find the about window
            about_windows = [child for child in root.winfo_children() if isinstance(child, tk.Toplevel)]
            assert len(about_windows) == 1
            about_window = cast("tk.Toplevel", about_windows[0])

            # Force the window to render and become visible on screen
            about_window.deiconify()
            about_window.lift()
            about_window.update_idletasks()
            about_window.update()

            # Verify: PyAutoGUI can capture a screenshot with the window visible
            screenshot = pyautogui.screenshot()
            assert screenshot is not None
            assert screenshot.size[0] > 0
            assert screenshot.size[1] > 0

            # Verify: Window geometry is within screen bounds
            _screen_width, _screen_height = pyautogui.size()
            win_x = about_window.winfo_x()
            win_y = about_window.winfo_y()
            win_width = about_window.winfo_width()
            win_height = about_window.winfo_height()

            assert win_width > 0, "Window should have positive width"
            assert win_height > 0, "Window should have positive height"
            # Note: win_x/win_y can be negative on CI (small virtual display)
            # or multi-monitor setups, so we only check the window is partially visible
            assert win_x + win_width > 0, "Window should be at least partially visible horizontally"
            assert win_y + win_height > 0, "Window should be at least partially visible vertically"

            # Verify: Window title is correct
            assert about_window.title() == "About"

            # Verify: Window is mapped (visible)
            assert about_window.winfo_ismapped(), "About window should be visible on screen"

            # Cleanup
            about_window.destroy()

        finally:
            root.destroy()

    def test_show_about_window(self, mocker) -> None:  # pylint: disable=too-many-locals
        """Test that the about window can be created."""
        # Create a mock root window
        root = tk.Tk()
        root.withdraw()  # Hide the root window

        try:
            # Mock webbrowser.open to avoid actually opening URLs
            mocker.patch("ardupilot_methodic_configurator.frontend_tkinter_about_popup_window.webbrowser_open_url")

            # Call the function
            show_about_window(root, "1.0.0")  # type: ignore[arg-type]

            # Find the about window (it should be a Toplevel child of root)
            about_windows = [child for child in root.winfo_children() if isinstance(child, tk.Toplevel)]

            # There should be exactly one about window
            assert len(about_windows) == 1
            about_window = cast("tk.Toplevel", about_windows[0])

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

    @pytest.mark.skip(reason="Requires manual GUI validation with real Tk root")
    def test_parameter_editor_initialization_without_tk_mocks(
        self,
        gui_test_environment,  # pylint: disable=unused-argument
        monkeypatch,
    ) -> None:
        """ParameterEditorWindow initializes against a real Tk root for PyAutoGUI flows."""
        param_editor = MagicMock()
        param_editor.current_file = "01_initial.param"
        param_editor.parameter_files.return_value = ["01_initial.param", "02_next.param"]
        param_editor.get_vehicle_directory.return_value = "gui-test-dir"
        param_editor.get_last_configuration_step_number.return_value = None
        param_editor.parameter_documentation_available.return_value = True
        param_editor.is_fc_connected = False
        param_editor.is_mavftp_supported = False
        param_editor.is_configuration_step_optional.return_value = False

        class DummyDirSelection:  # pylint: disable=too-few-public-methods
            """Stub directory selection widget for GUI integration tests."""

            def __init__(self, *_args, **_kwargs) -> None:
                self.container_frame = MagicMock()
                self.container_frame.pack = MagicMock()

        class DummyStageProgressBar:  # pylint: disable=too-few-public-methods
            """Minimal stage progress stub that records pack calls."""

            def __init__(self, *_args, **_kwargs) -> None:
                self.pack_calls: list[tuple[tuple, dict]] = []

            def pack(self, *args, **kwargs) -> None:
                self.pack_calls.append((args, kwargs))

        class DummyDocumentationFrame:
            """Simple documentation frame replacement with real ttk container."""

            def __init__(self, parent, _parameter_editor) -> None:
                self.documentation_frame = ttk.Frame(parent)

            def refresh_documentation_labels(self) -> None:
                return

            def update_why_why_now_tooltip(self) -> None:
                return

            def get_auto_open_documentation_in_browser(self) -> bool:
                return False

        class DummyParameterEditorTable:  # pylint: disable=too-few-public-methods
            """Lightweight table stub exposing the attributes the GUI touches."""

            def __init__(self, *_args, **_kwargs) -> None:
                self.view_port = MagicMock()
                self.pack_called = False

            def pack(self, *args, **_kwargs) -> None:  # pylint: disable=unused-argument
                self.pack_called = True

        def fake_get_setting(key: str) -> object:
            return {"gui_complexity": "normal", "annotate_docs_into_param_files": False}.get(key, False)

        def create_progress_window(*_args, **_kwargs) -> MagicMock:
            progress = MagicMock()
            progress.update_progress_bar = MagicMock()
            progress.update_progress_bar_300_pct = MagicMock()
            progress.destroy = MagicMock()
            return progress

        ui_services = ParameterEditorUiServices(
            create_progress_window=create_progress_window,
            ask_yesno=lambda *_a, **_k: True,
            ask_retry_cancel=lambda *_a, **_k: True,
            show_warning=lambda *_a, **_k: None,
            show_error=lambda *_a, **_k: None,
            show_info=lambda *_a, **_k: None,
            asksaveasfilename=lambda *_a, **_k: "",
            askopenfilename=lambda *_a, **_k: "",
            exit_callback=lambda _code: None,
        )

        monkeypatch.setattr(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ProgramSettings.get_setting",
            fake_get_setting,
        )
        monkeypatch.setattr(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.VehicleDirectorySelectionWidgets",
            DummyDirSelection,
        )
        monkeypatch.setattr(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.StageProgressBar",
            DummyStageProgressBar,
        )
        monkeypatch.setattr(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.DocumentationFrame",
            DummyDocumentationFrame,
        )
        monkeypatch.setattr(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ParameterEditorTable",
            DummyParameterEditorTable,
        )
        monkeypatch.setattr(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.FreeDesktop.setup_startup_notification",
            lambda *_a, **_k: None,
        )
        monkeypatch.setattr(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.UsagePopupWindow.should_display",
            lambda *_a, **_k: False,
        )
        monkeypatch.setattr(
            (
                "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ParameterEditorWindow."
                "repopulate_parameter_table"
            ),
            MagicMock(),
        )

        def fake_label(_parent, _filepath, *_args, **_kwargs) -> MagicMock:
            label = MagicMock()
            label.pack = MagicMock()
            label.bind = MagicMock()
            return label

        monkeypatch.setattr(
            "ardupilot_methodic_configurator.frontend_tkinter_parameter_editor.ParameterEditorWindow.put_image_in_label",
            fake_label,
        )

        window = ParameterEditorWindow(param_editor, ui_services=ui_services)

        try:
            assert isinstance(window.root, tk.Tk)
            assert window.root.winfo_exists()
            after_ids = window.root.tk.call("after", "info")
            assert after_ids, "Expected scheduled callbacks for initial workflows"
        finally:
            window.root.destroy()
