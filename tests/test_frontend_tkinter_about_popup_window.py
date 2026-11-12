#!/usr/bin/env python3

"""
Behavior-driven tests for the frontend_tkinter_about_popup_window.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk  # pylint: disable=unused-import
from typing import cast
from unittest.mock import patch
from urllib.parse import urlparse

import pytest

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem_program_settings import USAGE_POPUP_WINDOWS
from ardupilot_methodic_configurator.frontend_tkinter_about_popup_window import AboutWindow


def _create_about_window(
    root: tk.Tk, version: str = "1.2.3", popup_preferences: dict[str, bool] | None = None, dpi_scaling: float = 1.0
) -> AboutWindow:
    """Helper to create an AboutWindow with all heavy operations mocked."""
    with (
        patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow._setup_application_icon"),
        patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow._setup_theme_and_styling"),
        patch(
            "ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow._get_dpi_scaling_factor",
            return_value=dpi_scaling,
        ),
        patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow.center_window"),
        patch(
            "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.display_usage_popup",
            side_effect=lambda popup_id: True if popup_preferences is None else popup_preferences[popup_id],
        ),
    ):
        return AboutWindow(root, version)


def _has_padding(padding: int | tuple[int, int]) -> bool:
    """Accept positive symmetric or asymmetric Tk padding."""
    return all(value > 0 for value in padding) if isinstance(padding, tuple) else padding > 0


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
        assert window.root.title() == _("About")
        assert window.root.master is root

    def test_about_window_is_centered_on_its_parent(self, root: tk.Tk) -> None:
        """
        The About window opens relative to the window from which it was requested.

        GIVEN: A user opens About from the application window
        WHEN: The About window is created
        THEN: It is centered relative to that parent
        """
        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow._setup_application_icon"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow._setup_theme_and_styling"),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow._get_dpi_scaling_factor",
                return_value=1.0,
            ),
            patch("ardupilot_methodic_configurator.frontend_tkinter_base_window.BaseWindow.center_window") as center,
            patch(
                "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.display_usage_popup",
                return_value=True,
            ),
        ):
            window = AboutWindow(root, "1.2.3")
            center.assert_called_once_with(window.root, root)

    def test_about_window_scales_its_size_for_high_dpi_displays(self, root: tk.Tk) -> None:
        """
        The About window requests a larger size on high-DPI displays.

        GIVEN: A user opens About at standard and high display scaling
        WHEN: The windows are created
        THEN: Their requested width and height both scale with the display
        """
        sizes = []
        for scaling in (1.0, 1.5):
            with patch.object(tk.Toplevel, "geometry", autospec=True) as request_geometry:
                window = _create_about_window(root, dpi_scaling=scaling)
            request_geometry.assert_called_once()
            assert request_geometry.call_args.args[0] is window.root
            width, height = request_geometry.call_args.args[1].split("x")
            sizes.append((int(width), int(height)))
            window.root.destroy()

        assert all(dimension > 0 for dimension in sizes[0])
        # Keep the dialog's five-to-three aspect ratio at standard DPI.
        assert sizes[0][0] * 3 == sizes[0][1] * 5
        for standard, high_dpi in zip(*sizes, strict=True):
            assert abs(high_dpi - standard * 1.5) <= 1

    def test_about_sections_remain_distinct_and_readable(self, root: tk.Tk) -> None:
        """
        Users can distinguish the application information, preferences, and actions.

        GIVEN: The About window is open
        WHEN: The user views the information and popup preferences
        THEN: Both sections span the action area and appear above the action buttons
        AND: The preferences have a visible heading and vertically arranged checkboxes
        """
        window = _create_about_window(root)
        children = window.main_frame.winfo_children()
        buttons = [cast("ttk.Button", child) for child in children if child.winfo_class() == "TButton"]
        information = next(cast("ttk.Label", child) for child in children if child.winfo_class() == "TLabel")
        preferences = next(cast("ttk.Frame", child) for child in children if child.winfo_class() == "TFrame")
        button_positions = [button.grid_info() for button in buttons]
        info_position = information.grid_info()
        preference_position = preferences.grid_info()
        assert len(buttons) == 5
        assert info_position["row"] < preference_position["row"] < button_positions[0]["row"]
        for position in (info_position, preference_position):
            assert position["column"] == min(item["column"] for item in button_positions)
            assert position["columnspan"] == len(buttons)
            assert _has_padding(position["padx"])
            assert _has_padding(position["pady"])
        assert info_position["padx"] == preference_position["padx"]
        assert info_position["pady"] == preference_position["pady"]
        assert int(information.cget("wraplength")) > 0

        preference_children = preferences.winfo_children()
        heading = next(cast("ttk.Label", child) for child in preference_children if child.winfo_class() == "TLabel")
        checkboxes = [cast("ttk.Checkbutton", child) for child in preference_children if child.winfo_class() == "TCheckbutton"]
        assert heading.cget("text") == _("Display usage popup")
        assert heading.pack_info()["side"] == "top"
        assert checkboxes
        assert all(checkbox.pack_info()["side"] == "top" for checkbox in checkboxes)
        assert all(checkbox.pack_info()["anchor"] == heading.pack_info()["anchor"] for checkbox in checkboxes)

    def test_about_information_fits_a_narrow_window_with_a_large_font(self, root: tk.Tk) -> None:
        """
        About information remains readable with a larger font in a narrow window.

        GIVEN: The user opens About with a large Bitstream Charter font
        WHEN: The available window width is 472 pixels
        THEN: The wrapped information and its margins fit within that width
        """
        families = {family.casefold(): family for family in tkfont.families(root)}
        family = families.get("bitstream charter")
        if family is None:
            pytest.skip("Bitstream Charter is not installed")

        window = _create_about_window(root, version="1.2.3")
        information = next(
            cast("ttk.Label", child) for child in window.main_frame.winfo_children() if child.winfo_class() == "TLabel"
        )
        large_font = tkfont.Font(root=root, family=family, size=21)
        # The clipping boundary depends on the platform's font rasterizer and DPI.
        if (
            large_font.measure("ArduPilot Methodic Configurator Version: 1.2.3") != 605
            or large_font.measure("Licensed under the GNU General Public License v3.0") != 667
        ):
            pytest.skip("Bitstream Charter font metrics do not match the narrow-window scenario")
        information.configure(font=large_font)
        window.root.geometry("472x390")
        padding = information.grid_info()["padx"]
        horizontal_margin = sum(padding) if isinstance(padding, tuple) else 2 * padding
        assert information.winfo_reqwidth() + horizontal_margin <= 472

    def test_about_action_labels_identify_their_resources(self, root: tk.Tk) -> None:
        """
        Users can identify each available About action.

        GIVEN: The About window is open
        WHEN: The user reads the action buttons
        THEN: Each button displays its translated resource name
        """
        window = _create_about_window(root)
        labels = {str(child.cget("text")) for child in window.main_frame.winfo_children() if child.winfo_class() == "TButton"}
        assert labels == {_("User Manual"), _("Support Forum"), _("Report a Bug"), _("Licenses"), _("Source Code")}

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

    def test_user_can_read_application_identity_and_license(self, root: tk.Tk) -> None:
        """
        The About window identifies the application and its license.

        GIVEN: The application is running a known version
        WHEN: The user reads the About information
        THEN: The version, copyright holders, and GPL version are shown clearly
        """
        window = _create_about_window(root, version="3.0.5")
        label = next(child for child in window.main_frame.winfo_children() if child.winfo_class() == "TLabel")
        paragraphs = str(label.cget("text")).split("\n\n")
        assert paragraphs[0] == "ArduPilot Methodic Configurator Version: 3.0.5"
        assert paragraphs[1] == "A clear configuration sequence for ArduPilot vehicles."
        assert paragraphs[2].startswith("Copyright © ")
        assert paragraphs[2].endswith(" Amilcar do Carmo Lucas and ArduPilot.org")
        assert paragraphs[3] == "Licensed under the GNU General Public License v3.0"

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

    def test_about_action_buttons_do_not_overlap(self, root: tk.Tk) -> None:
        """
        The user can see and select every About action.

        GIVEN: The About window is open
        WHEN: The action buttons are displayed
        THEN: They occupy distinct columns in the same row
        """
        window = _create_about_window(root)
        buttons = [widget for widget in window.main_frame.winfo_children() if widget.winfo_class() == "TButton"]
        assert len(buttons) == 5
        positions = [cast("ttk.Button", button).grid_info() for button in buttons]
        assert all(positions)
        assert len({position["row"] for position in positions}) == 1
        assert len({position["column"] for position in positions}) == len(buttons)

    def test_about_actions_have_space_and_expand_evenly(self, root: tk.Tk) -> None:
        """
        About actions remain distinct and evenly distributed when the window expands.

        GIVEN: The About window displays its resource actions
        WHEN: The user views or resizes the window
        THEN: Every action has space around it and its column expands equally
        """
        window = _create_about_window(root)
        buttons = [
            cast("ttk.Button", child) for child in window.main_frame.winfo_children() if child.winfo_class() == "TButton"
        ]
        assert len(buttons) == 5
        positions = [button.grid_info() for button in buttons]
        assert all(_has_padding(position["padx"]) and _has_padding(position["pady"]) for position in positions)
        assert len({position["padx"] for position in positions}) == 1
        assert len({position["pady"] for position in positions}) == 1
        weights = [window.main_frame.grid_columnconfigure(position["column"])["weight"] for position in positions]
        assert all(weight > 0 for weight in weights)
        assert len(set(weights)) == 1

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
                        cast("ttk.Button", widget).invoke()
                        return
                except tk.TclError:
                    pass
        children = [w.winfo_class() for w in window.main_frame.winfo_children()]
        msg = f"No TButton containing '{text_fragment}' found among main_frame children: {children}"
        raise AssertionError(msg)

    @pytest.mark.parametrize(
        ("button", "url"),
        [
            ("Manual", "https://github.com/ArduPilot/MethodicConfigurator/blob/master/USERMANUAL.md"),
            ("Support", "http://discuss.ardupilot.org/t/new-ardupilot-methodic-configurator-gui/115038/1"),
            ("Bug", "https://github.com/ArduPilot/MethodicConfigurator/issues/new/choose"),
            ("License", "https://github.com/ArduPilot/MethodicConfigurator/blob/master/credits/CREDITS.md"),
            ("Source", "https://github.com/ArduPilot/MethodicConfigurator"),
        ],
    )
    def test_user_opens_the_requested_resource(self, root: tk.Tk, button: str, url: str) -> None:
        """
        Each About action opens its intended resource.

        GIVEN: The user has opened the About window
        WHEN: They choose an action
        THEN: The browser opens the matching project resource
        """
        window = _create_about_window(root)
        with patch("ardupilot_methodic_configurator.frontend_tkinter_about_popup_window.webbrowser_open_url") as open_url:
            self._find_button_by_text(window, button)
            open_url.assert_called_once_with(url)

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

    def test_each_checkbox_reflects_and_updates_its_own_preference(self, root: tk.Tk) -> None:
        """
        Each usage popup preference can be viewed and changed independently.

        GIVEN: Usage popups have alternating enabled and disabled preferences
        WHEN: The user opens About and toggles each preference twice
        THEN: Each checkbox shows its saved state and updates the corresponding popup in both directions
        """
        preferences = {popup_id: index % 2 == 0 for index, popup_id in enumerate(USAGE_POPUP_WINDOWS)}
        window = _create_about_window(root, popup_preferences=preferences)
        checkboxes = {
            str(child.cget("text")): child
            for frame in window.main_frame.winfo_children()
            if frame.winfo_class() in ("TFrame", "Frame")
            for child in frame.winfo_children()
            if child.winfo_class() in ("TCheckbutton", "Checkbutton")
        }

        with patch(
            "ardupilot_methodic_configurator.backend_filesystem_program_settings.ProgramSettings.set_display_usage_popup"
        ) as save_preference:
            for popup_id, popup in USAGE_POPUP_WINDOWS.items():
                checkbox = cast("ttk.Checkbutton", checkboxes[popup.description])
                initial = preferences[popup_id]
                assert bool(checkbox.instate(["selected"])) is initial
                checkbox.invoke()
                save_preference.assert_called_with(popup_id, not initial)
                assert bool(checkbox.instate(["selected"])) is (not initial)
                checkbox.invoke()
                save_preference.assert_called_with(popup_id, initial)
                assert bool(checkbox.instate(["selected"])) is initial

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
                            cast("ttk.Checkbutton", child).invoke()
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
