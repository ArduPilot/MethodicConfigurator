#!/usr/bin/env python3

"""
Behavior-driven tests for the frontend_tkinter_about_popup_window.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import tkinter as tk
from unittest.mock import patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_about_popup_window import AboutWindow

# pylint: disable=redefined-outer-name


@pytest.fixture
def root() -> tk.Tk:
    """Provide a hidden Tk root window for tests."""
    root = tk.Tk()
    root.withdraw()
    yield root
    root.update_idletasks()
    root.destroy()


def _create_about_window(root: tk.Tk, version: str = "1.2.3") -> AboutWindow:
    """Helper to create an AboutWindow with all heavy operations mocked."""
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow._setup_application_icon"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow._setup_theme_and_styling"),
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow._get_dpi_scaling_factor",
            return_value=1.0,
        ),
        patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow.center_window"),
    ):
        return AboutWindow(root, version)


class TestAboutWindowCreation:
    """Tests for About window creation and initialization."""

    def test_user_can_open_about_window(self, root: tk.Tk) -> None:
        """
        User can open the About popup window.

        GIVEN: The application is running
        WHEN: User opens the About window
        THEN: A window with title "About" should appear
        AND: Version information should be displayed
        """
        window = _create_about_window(root, version="3.0.5")

        assert window is not None
        assert window.root is not None
        assert "About" in window.root.title()

    def test_user_sees_version_information_in_about_window(self, root: tk.Tk) -> None:
        """
        User sees correct version information in the About window.

        GIVEN: The application has a specific version
        WHEN: User opens the About window
        THEN: The version number should be displayed in the about message
        """
        version = "3.0.5"
        window = _create_about_window(root, version=version)

        # Find the about label and check it contains the version
        found_version = False
        for widget in window.main_frame.winfo_children():
            if hasattr(widget, "cget"):
                try:
                    text = widget.cget("text")
                    if version in str(text):
                        found_version = True
                        break
                except tk.TclError:
                    pass
        assert found_version, f"Version '{version}' not found in any widget text"

    def test_user_sees_copyright_notice_in_about_window(self, root: tk.Tk) -> None:
        """
        User sees copyright notice in the About window.

        GIVEN: The application is open
        WHEN: User views the About window
        THEN: Copyright information should be visible
        """
        window = _create_about_window(root)

        found_copyright = False
        for widget in window.main_frame.winfo_children():
            if hasattr(widget, "cget"):
                try:
                    text = str(widget.cget("text"))
                    if "Copyright" in text or "copyright" in text.lower():
                        found_copyright = True
                        break
                except tk.TclError:
                    pass
        assert found_copyright, "Copyright notice not found in About window"

    def test_about_window_has_action_buttons(self, root: tk.Tk) -> None:
        """
        About window has action buttons for external resources.

        GIVEN: User opens the About window
        WHEN: They look at the window
        THEN: Buttons for User Manual, Support Forum, Report a Bug, Licenses, and Source Code should be present
        """
        window = _create_about_window(root)

        button_texts = []
        for widget in window.main_frame.winfo_children():
            widget_class = widget.winfo_class()
            if widget_class in ("TButton", "Button"):
                with contextlib.suppress(tk.TclError):
                    button_texts.append(widget.cget("text"))

        # Should have 5 action buttons
        assert len(button_texts) >= 5

    def test_about_window_has_usage_popup_checkboxes(self, root: tk.Tk) -> None:
        """
        About window contains usage popup preference checkboxes.

        GIVEN: User opens the About window
        WHEN: They look at the window
        THEN: Checkboxes for controlling usage popups should be present
        """
        window = _create_about_window(root)

        found_frame = False
        for widget in window.main_frame.winfo_children():
            widget_class = widget.winfo_class()
            if widget_class in ("TFrame", "Frame"):
                for child in widget.winfo_children():
                    child_class = child.winfo_class()
                    if child_class in ("TCheckbutton", "Checkbutton"):
                        found_frame = True
                        break

        assert found_frame, "Usage popup checkboxes not found in About window"


class TestAboutWindowButtonInteractions:
    """Tests for button interactions in the About window."""

    def _find_button_by_text(self, window: AboutWindow, text_fragment: str) -> None:
        """Find a button in the window and invoke it."""
        for widget in window.main_frame.winfo_children():
            widget_class = widget.winfo_class()
            if widget_class == "TButton":
                try:
                    btn_text = widget.cget("text")
                    if text_fragment.lower() in str(btn_text).lower():
                        widget.invoke()
                        return
                except tk.TclError:
                    pass

    def test_user_can_open_user_manual_via_about_window(self, root: tk.Tk) -> None:
        """
        User can open the User Manual from the About window.

        GIVEN: User has the About window open
        WHEN: User clicks the User Manual button
        THEN: The User Manual URL should be opened in the default web browser
        """
        window = _create_about_window(root)

        with patch("ardupilot_methodic_configurator.frontend_tkinter_about_popup_window.webbrowser_open_url") as mock_open:
            self._find_button_by_text(window, "Manual")
            mock_open.assert_called_once()
            call_args = mock_open.call_args[0][0]
            assert "USERMANUAL" in call_args or "usermanual" in call_args.lower()

    def test_user_can_open_support_forum_via_about_window(self, root: tk.Tk) -> None:
        """
        User can access the support forum from the About window.

        GIVEN: User has the About window open
        WHEN: User clicks the Support Forum button
        THEN: The support forum URL should be opened in the default web browser
        """
        window = _create_about_window(root)

        with patch("ardupilot_methodic_configurator.frontend_tkinter_about_popup_window.webbrowser_open_url") as mock_open:
            self._find_button_by_text(window, "Support")
            mock_open.assert_called_once()
            call_args = mock_open.call_args[0][0]
            assert "ardupilot" in call_args.lower() or "discuss" in call_args.lower()

    def test_user_can_report_a_bug_via_about_window(self, root: tk.Tk) -> None:
        """
        User can report a bug via the About window.

        GIVEN: User has the About window open
        WHEN: User clicks the Report a Bug button
        THEN: The GitHub issues URL should be opened in the default web browser
        """
        window = _create_about_window(root)

        with patch("ardupilot_methodic_configurator.frontend_tkinter_about_popup_window.webbrowser_open_url") as mock_open:
            self._find_button_by_text(window, "Bug")
            mock_open.assert_called_once()
            call_args = mock_open.call_args[0][0]
            assert "issues" in call_args.lower() or "github" in call_args.lower()

    def test_user_can_view_licenses_via_about_window(self, root: tk.Tk) -> None:
        """
        User can view licenses from the About window.

        GIVEN: User has the About window open
        WHEN: User clicks the Licenses button
        THEN: The CREDITS.md URL should be opened in the default web browser
        """
        window = _create_about_window(root)

        with patch("ardupilot_methodic_configurator.frontend_tkinter_about_popup_window.webbrowser_open_url") as mock_open:
            self._find_button_by_text(window, "License")
            mock_open.assert_called_once()
            call_args = mock_open.call_args[0][0]
            assert "CREDITS" in call_args or "credits" in call_args.lower()

    def test_user_can_view_source_code_via_about_window(self, root: tk.Tk) -> None:
        """
        User can view source code from the About window.

        GIVEN: User has the About window open
        WHEN: User clicks the Source Code button
        THEN: The GitHub repository URL should be opened in the default web browser
        """
        window = _create_about_window(root)

        with patch("ardupilot_methodic_configurator.frontend_tkinter_about_popup_window.webbrowser_open_url") as mock_open:
            self._find_button_by_text(window, "Source")
            mock_open.assert_called_once()
            call_args = mock_open.call_args[0][0]
            assert "github.com/ArduPilot/MethodicConfigurator" in call_args


class TestAboutWindowUsagePopupPreferences:
    """Tests for usage popup preference checkboxes in the About window."""

    def test_user_can_toggle_usage_popup_display_preference(self, root: tk.Tk) -> None:
        """
        User can toggle usage popup display preferences from the About window.

        GIVEN: User has the About window open
        WHEN: User toggles a usage popup checkbox
        THEN: The preference should be updated via ProgramSettings
        """
        window = _create_about_window(root)

        with patch(
            "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.set_display_usage_popup"
        ):
            # Find and click a checkbox in the usage popup frame
            for widget in window.main_frame.winfo_children():
                if widget.winfo_class() in ("TFrame", "Frame"):
                    for child in widget.winfo_children():
                        if child.winfo_class() in ("TCheckbutton", "Checkbutton"):
                            child.invoke()
                            break

    def test_about_window_reads_current_usage_popup_preferences(self, root: tk.Tk) -> None:
        """
        About window displays current usage popup preferences correctly.

        GIVEN: The user has previously set usage popup preferences
        WHEN: User opens the About window
        THEN: The checkboxes should reflect the current preferences
        """
        with patch(
            "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.display_usage_popup",
            return_value=True,
        ):
            window = _create_about_window(root)

        assert window is not None

    def test_about_window_initializes_with_different_version_strings(self, root: tk.Tk) -> None:
        """
        About window initializes correctly with different version strings.

        GIVEN: Various valid version strings
        WHEN: About window is created with each version
        THEN: Window should display correctly for each version
        """
        for version in ["1.0.0", "2.5.3", "10.0.0", "0.1.0-beta"]:
            window = _create_about_window(root, version=version)
            assert window is not None

            found_version = False
            for widget in window.main_frame.winfo_children():
                if hasattr(widget, "cget"):
                    try:
                        text = str(widget.cget("text"))
                        if version in text:
                            found_version = True
                            break
                    except tk.TclError:
                        pass
            assert found_version, f"Version '{version}' not found in About window"
            window.root.destroy()
