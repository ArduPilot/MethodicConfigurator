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
from urllib.parse import urlparse

from ardupilot_methodic_configurator.frontend_tkinter_about_popup_window import AboutWindow


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
        patch(
            "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.display_usage_popup",
            return_value=True,
        ),
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

        # Verify specific button labels exist
        button_labels_lower = [b.lower() for b in button_texts]
        assert any("manual" in b for b in button_labels_lower), f"User Manual button not found in: {button_texts}"
        assert any("support" in b or "forum" in b for b in button_labels_lower), (
            f"Support Forum button not found in: {button_texts}"
        )
        assert any("bug" in b or "issue" in b for b in button_labels_lower), f"Report Bug button not found in: {button_texts}"
        assert any("license" in b or "credit" in b for b in button_labels_lower), (
            f"Licenses button not found in: {button_texts}"
        )
        assert any("source" in b or "code" in b for b in button_labels_lower), (
            f"Source Code button not found in: {button_texts}"
        )

    def test_about_window_has_usage_popup_checkboxes(self, root: tk.Tk) -> None:
        """
        About window contains usage popup preference checkboxes.

        GIVEN: User opens the About window
        WHEN: They look at the window
        THEN: Checkboxes for controlling usage popups should be present
        """
        window = _create_about_window(root)

        checkbox_count = 0
        for widget in window.main_frame.winfo_children():
            widget_class = widget.winfo_class()
            if widget_class in ("TFrame", "Frame"):
                for child in widget.winfo_children():
                    child_class = child.winfo_class()
                    if child_class in ("TCheckbutton", "Checkbutton"):
                        checkbox_count += 1

        assert checkbox_count > 0, f"Usage popup checkboxes not found in About window (found {checkbox_count})"


class TestAboutWindowButtonInteractions:
    """Tests for button interactions in the About window."""

    def _find_button_by_text(self, window: AboutWindow, text_fragment: str) -> None:
        """Find a button in the window and invoke it. Raises AssertionError if not found."""
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
        children = [w.winfo_class() for w in window.main_frame.winfo_children()]
        msg = f"No TButton containing '{text_fragment}' found among main_frame children: {children}"
        raise AssertionError(msg)

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
            assert isinstance(call_args, str), f"Expected URL string but got {type(call_args)}"
            assert "USERMANUAL" in call_args or "usermanual" in call_args.lower(), f"User Manual URL not found in {call_args}"
            assert call_args.startswith("http"), f"URL should start with http but got {call_args}"

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
            assert isinstance(call_args, str), f"Expected URL string but got {type(call_args)}"
            call_args_lower = call_args.lower()
            assert "ardupilot" in call_args_lower or "discuss" in call_args_lower, (
                f"Support forum URL not found in {call_args}"
            )
            assert call_args.startswith("http"), f"URL should start with http but got {call_args}"

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
            assert isinstance(call_args, str), f"Expected URL string but got {type(call_args)}"
            call_args_lower = call_args.lower()
            assert "issues" in call_args_lower or "bug" in call_args_lower, f"Issues URL not found in {call_args}"
            parsed_url = urlparse(call_args)
            host = parsed_url.hostname
            assert host is not None, f"GitHub URL host not found in {call_args}"
            assert host == "github.com" or host.endswith(".github.com"), f"GitHub URL not found in {call_args}"
            assert call_args.startswith("http"), f"URL should start with http but got {call_args}"

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
            assert isinstance(call_args, str), f"Expected URL string but got {type(call_args)}"
            call_args_lower = call_args.lower()
            assert "credits" in call_args_lower, f"CREDITS URL not found in {call_args}"
            assert call_args.startswith("http"), f"URL should start with http but got {call_args}"

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
            assert isinstance(call_args, str), f"Expected URL string but got {type(call_args)}"
            assert call_args.startswith("http"), f"URL should start with http but got {call_args}"
            parsed_url = urlparse(call_args)
            host = parsed_url.hostname
            assert host is not None, f"GitHub URL host not found in {call_args}"
            assert host == "github.com" or host.endswith(".github.com"), f"GitHub URL not found in {call_args}"
            assert "ArduPilot/MethodicConfigurator" in parsed_url.path, f"Expected repository path not found in {call_args}"


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
        ) as mock_set:
            # Find and click a checkbox in the usage popup frame
            checkbox_invoked = False
            for widget in window.main_frame.winfo_children():
                if widget.winfo_class() in ("TFrame", "Frame"):
                    for child in widget.winfo_children():
                        if child.winfo_class() in ("TCheckbutton", "Checkbutton"):
                            child.invoke()
                            checkbox_invoked = True
                            break
            assert checkbox_invoked, "No checkbox found to invoke"
            mock_set.assert_called_once()

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

        # Verify window was created successfully
        assert window is not None
        assert window.root is not None
        # Verify that preferences were read by checking checkboxes exist
        checkbox_count = 0
        for widget in window.main_frame.winfo_children():
            if widget.winfo_class() in ("TFrame", "Frame"):
                for child in widget.winfo_children():
                    if child.winfo_class() in ("TCheckbutton", "Checkbutton"):
                        checkbox_count += 1
        assert checkbox_count > 0, "Preferences checkboxes should be present after initialization"

    def test_about_window_initializes_with_different_version_strings(self, root: tk.Tk) -> None:
        """
        About window initializes correctly with different version strings.

        GIVEN: Various valid version strings
        WHEN: About window is created with each version
        THEN: Window should display correctly for each version
        """
        versions = ["1.0.0", "2.5.3", "10.0.0", "0.1.0-beta"]
        for version in versions:
            window = _create_about_window(root, version=version)
            assert window is not None, f"Window creation failed for version {version}"
            assert window.root is not None, f"Window root is None for version {version}"

            found_version = False
            version_text = ""
            for widget in window.main_frame.winfo_children():
                if hasattr(widget, "cget"):
                    try:
                        text = str(widget.cget("text"))
                        if version in text:
                            found_version = True
                            version_text = text
                            break
                    except tk.TclError:
                        pass
            assert found_version, f"Version '{version}' not found in About window. Searched text: {version_text}"
            window.root.destroy()
