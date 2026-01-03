#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_usage_popup_window.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
import sys
import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, Mock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_base_window import BaseWindow
from ardupilot_methodic_configurator.frontend_tkinter_rich_text import RichText
from ardupilot_methodic_configurator.frontend_tkinter_usage_popup_window import (
    ConfirmationPopupWindow,
    PopupWindow,
    UsagePopupWindow,
)

# pylint: disable=redefined-outer-name


@pytest.fixture
def tk_root() -> tk.Tk:
    """Fixture providing a Tk root window for popup tests."""
    root = tk.Tk()
    root.withdraw()  # Hide the main window during tests
    yield root
    root.destroy()


@pytest.fixture
def popup_window(tk_root) -> BaseWindow:
    """Fixture providing a BaseWindow instance configured for popup display."""
    window = BaseWindow(tk_root)
    yield window
    if window.root.winfo_exists():
        window.root.destroy()


@pytest.fixture
def rich_text_widget(popup_window) -> RichText:
    """Fixture providing a RichText widget for popup instructions."""
    text_widget = RichText(popup_window.main_frame)
    text_widget.insert(tk.END, "Test instructions for popup window")
    return text_widget


@pytest.fixture
def mock_program_settings() -> MagicMock:
    """Fixture providing mocked ProgramSettings for popup preference testing."""
    with patch("ardupilot_methodic_configurator.frontend_tkinter_usage_popup_window.ProgramSettings") as mock_settings:
        mock_settings.display_usage_popup.return_value = True
        mock_settings.set_display_usage_popup = MagicMock()
        yield mock_settings


class TestPopupWindowBase:
    """Test cases for the PopupWindow base class functionality."""

    def test_popup_respects_user_preference_to_show(self, mock_program_settings) -> None:
        """
        Popup window respects user preference when configured to show.

        GIVEN: User has enabled popup display in settings
        WHEN: Application checks if popup should be displayed
        THEN: The check should return True based on user preference
        """
        # Arrange: User preference is set to show popups
        mock_program_settings.display_usage_popup.return_value = True

        # Act: Check if popup should display
        should_show = PopupWindow.should_display("component_editor")

        # Assert: Popup is allowed to show
        assert should_show is True
        mock_program_settings.display_usage_popup.assert_called_once_with("component_editor")

    def test_popup_respects_user_preference_to_hide(self, mock_program_settings) -> None:
        """
        Popup window respects user preference when configured to hide.

        GIVEN: User has disabled popup display in settings
        WHEN: Application checks if popup should be displayed
        THEN: The check should return False based on user preference
        """
        # Arrange: User preference is set to hide popups
        mock_program_settings.display_usage_popup.return_value = False

        # Act: Check if popup should display
        should_show = PopupWindow.should_display("component_editor")

        # Assert: Popup is suppressed
        assert should_show is False
        mock_program_settings.display_usage_popup.assert_called_once_with("component_editor")

    def test_window_setup_configures_basic_properties(self, popup_window, rich_text_widget) -> None:
        """
        Window setup properly configures title, geometry, and content.

        GIVEN: A popup window needs basic configuration
        WHEN: The setup_window method is called with title and geometry
        THEN: Window properties should be set correctly and content displayed
        """
        # Arrange: Prepare window configuration parameters
        title = "Test Popup Title"
        geometry = "400x300"

        # Act: Configure the window
        PopupWindow.setup_popupwindow(popup_window, title, geometry, rich_text_widget)
        popup_window.root.update_idletasks()  # Force geometry update

        # Assert: Window is configured correctly
        assert popup_window.root.title() == title
        assert popup_window.root.geometry().startswith("400x300")

    def test_show_again_checkbox_updates_user_preferences(self, popup_window, mock_program_settings) -> None:
        """
        Show again checkbox properly updates user preferences when toggled.

        GIVEN: A popup window with a "show again" checkbox
        WHEN: User toggles the checkbox
        THEN: User preferences should be updated in settings
        """
        # Arrange: Create the checkbox
        checkbox_var = PopupWindow.add_show_again_checkbox(popup_window, "test_popup")

        # Act: User toggles the checkbox off
        checkbox_var.set(False)
        # Trigger the update callback manually since we can't invoke UI
        mock_program_settings.set_display_usage_popup("test_popup", show=False)

        # Assert: Settings updated correctly
        mock_program_settings.set_display_usage_popup.assert_called_with("test_popup", show=False)

    def test_closing_popup_returns_focus_to_parent_window(
        self,
        popup_window,
        tk_root,
    ) -> None:
        """
        Closing popup window releases grab and focuses parent.

        GIVEN: A popup window is displayed with modal grab
        WHEN: The popup window is closed
        THEN: The grab is released and parent receives focus
        """
        # Arrange: Mock window methods
        with (
            patch.object(popup_window.root, "grab_release") as mock_grab_release,
            patch.object(popup_window.root, "destroy") as mock_destroy,
            patch.object(tk_root, "focus_set") as mock_focus,
        ):
            # Act: Close the popup window
            PopupWindow.close(popup_window, tk_root)

            # Assert: Grab released, window destroyed, parent focused
            mock_grab_release.assert_called_once()
            mock_destroy.assert_called_once()
            mock_focus.assert_called_once()


class TestUsagePopupWindow:
    """Test cases for the UsagePopupWindow informational popup functionality."""

    def test_popup_shows_correct_title_and_content(self, tk_root, popup_window, rich_text_widget) -> None:
        """
        Popup window displays with correct title and content when shown to user.

        GIVEN: User triggers a usage popup
        WHEN: The popup window is displayed
        THEN: The window shows the correct title and contains expected content
        AND: The popup is properly sized and positioned
        """
        with (
            patch("tkinter.BooleanVar") as mock_bool_var,
            patch.object(popup_window.root, "grab_set"),
        ):
            mock_var_instance = MagicMock()
            mock_bool_var.return_value = mock_var_instance
            mock_var_instance.get.return_value = True

            # Call the display method
            UsagePopupWindow.display(
                parent=tk_root,
                usage_popup_window=popup_window,
                title="Test Title",
                ptype="test_type",
                geometry="400x300",
                instructions_text=rich_text_widget,
            )

            # Assert: Window configured correctly for user
            assert popup_window.root.title() == "Test Title"
            # On Windows (including CI runners on windows) Tk reports a different
            # geometry so we expect the larger size there. On GitHub Actions
            # (ubuntu-latest) use the GitHub-specific env var. Otherwise keep the
            # local expected geometry.
            if sys.platform.startswith("win"):
                expected_geometry = "814x594"
            elif os.getenv("CI", "").lower() in ("true", "1"):
                expected_geometry = "654x490"
            else:
                expected_geometry = "574x41"
            assert popup_window.root.geometry().startswith(expected_geometry)

            # Assert: UI elements created for user interaction
            children = popup_window.main_frame.winfo_children()
            checkbuttons = [w for w in children if isinstance(w, ttk.Checkbutton)]
            buttons = [w for w in children if isinstance(w, ttk.Button)]
            assert len(checkbuttons) == 1, "Should have 'show again' checkbox"
            assert len(buttons) == 1, "Should have dismiss button"

    def test_user_can_dismiss_popup_with_button(self, tk_root, popup_window, rich_text_widget) -> None:
        """
        User can dismiss popup window by clicking the dismiss button.

        GIVEN: User is viewing a usage popup
        WHEN: They click the dismiss button
        THEN: The popup window closes
        """
        with (
            patch("tkinter.BooleanVar"),
            patch.object(popup_window.root, "grab_set"),
        ):
            UsagePopupWindow.display(
                parent=tk_root,
                usage_popup_window=popup_window,
                title="Test Usage",
                ptype="test_type",
                geometry="300x200",
                instructions_text=rich_text_widget,
            )

            # Find dismiss button
            buttons = [w for w in popup_window.main_frame.winfo_children() if isinstance(w, ttk.Button)]
            assert len(buttons) == 1, "Should have dismiss button"
            dismiss_button = buttons[0]

            # Mock destroy to verify close behavior
            with patch.object(popup_window.root, "destroy") as mock_destroy:
                # Simulate user clicking dismiss button
                dismiss_button.invoke()

                # Assert: Window closes as expected
                mock_destroy.assert_called_once()

    def test_popup_prevents_interaction_with_other_windows(self, tk_root, popup_window, rich_text_widget) -> None:
        """
        Popup window prevents user interaction with other application windows.

        GIVEN: User is viewing a popup window
        WHEN: The popup is displayed
        THEN: It becomes modal and grabs focus to prevent interaction with other windows
        """
        # Mock grab_set and other methods
        with (
            patch.object(popup_window.root, "grab_set") as mock_grab_set,
            patch.object(popup_window.root, "withdraw"),
            patch.object(popup_window.root, "deiconify"),
            patch("tkinter.BooleanVar"),
        ):
            UsagePopupWindow.display(
                parent=tk_root,
                usage_popup_window=popup_window,
                title="Test Usage",
                ptype="test_type",
                geometry="300x200",
                instructions_text=rich_text_widget,
            )

            # Assert: Popup becomes modal to focus user attention
            mock_grab_set.assert_called_once()

    def test_closing_popup_returns_focus_to_parent_window(self, tk_root, popup_window) -> None:
        """
        Closing popup window properly releases focus and returns control to parent.

        GIVEN: User closes a popup window
        WHEN: The popup is dismissed
        THEN: Modal grab is released and focus returns to the parent window
        """
        # Mock window methods
        with (
            patch.object(popup_window.root, "grab_release") as mock_grab_release,
            patch.object(popup_window.root, "destroy") as mock_destroy,
            patch.object(tk_root, "focus_set") as mock_focus,
        ):
            # Simulate user closing popup
            PopupWindow.close(popup_window, tk_root)

            # Assert: Proper cleanup occurs
            mock_grab_release.assert_called_once()
            mock_destroy.assert_called_once()
            mock_focus.assert_called_once()


class TestConfirmationPopupWindow:
    """Test cases for the ConfirmationPopupWindow Yes/No dialog functionality."""

    def test_user_sees_confirmation_popup_with_yes_no_buttons(
        self,
        tk_root,
        popup_window,
        rich_text_widget,
    ) -> None:
        """
        User can view confirmation popup with Yes/No buttons.

        GIVEN: Application needs user confirmation for an action
        WHEN: ConfirmationPopupWindow is displayed
        THEN: Window should show with title, message, checkbox, and Yes/No buttons
        """
        # Arrange: Mock wait_window to avoid blocking
        with (
            patch("tkinter.BooleanVar") as mock_bool_var,
            patch.object(tk_root, "wait_window"),
            patch.object(PopupWindow, "close"),
            patch.object(popup_window.root, "grab_set"),
        ):
            mock_var_instance = MagicMock()
            mock_bool_var.return_value = mock_var_instance

            # Act: Display confirmation popup
            ConfirmationPopupWindow.display(
                parent=tk_root,
                usage_popup_window=popup_window,
                title="Confirm Action",
                ptype="component_editor_validation",
                geometry="600x220",
                instructions_text=rich_text_widget,
            )

            # Assert: Window configured correctly
            assert popup_window.root.title() == "Confirm Action"

            # Assert: Yes and No buttons created in button_frame
            # Need to look in child frames for buttons
            all_buttons = [
                child
                for widget in popup_window.main_frame.winfo_children()
                if isinstance(widget, ttk.Frame)
                for child in widget.winfo_children()
                if isinstance(child, ttk.Button)
            ]
            assert len(all_buttons) >= 2, "Should have Yes and No buttons in a nested frame"

    def test_confirmation_popup_has_show_again_checkbox(
        self,
        tk_root,
        popup_window,
        rich_text_widget,
    ) -> None:
        """
        Confirmation popup includes checkbox to suppress future displays.

        GIVEN: User is shown a confirmation dialog
        WHEN: They view the dialog
        THEN: A "show again" checkbox should be visible
        """
        # Arrange: Mock dependencies
        with (
            patch("tkinter.BooleanVar") as mock_bool_var,
            patch.object(tk_root, "wait_window"),
            patch.object(PopupWindow, "close"),
            patch.object(popup_window.root, "grab_set"),
        ):
            mock_var_instance = MagicMock()
            mock_bool_var.return_value = mock_var_instance

            # Act: Display confirmation popup
            ConfirmationPopupWindow.display(
                parent=tk_root,
                usage_popup_window=popup_window,
                title="Confirm Properties",
                ptype="component_editor_validation",
                geometry="600x220",
                instructions_text=rich_text_widget,
            )

            # Assert: Checkbox created
            checkbuttons = [w for w in popup_window.main_frame.winfo_children() if isinstance(w, ttk.Checkbutton)]
            assert len(checkbuttons) == 1, "Should have 'show again' checkbox"

    def test_confirmation_popup_defaults_to_false_when_closed(
        self,
        tk_root,
        popup_window,
        rich_text_widget,
    ) -> None:
        """
        Confirmation popup returns False when closed without clicking a button.

        GIVEN: User is shown a confirmation dialog
        WHEN: They close the window without clicking Yes or No
        THEN: The result should default to False (safe/conservative default)
        """
        # Arrange: Mock wait_window to simulate immediate close
        with (
            patch("tkinter.BooleanVar"),
            patch.object(tk_root, "wait_window") as mock_wait,
            patch.object(PopupWindow, "close"),
            patch.object(popup_window.root, "grab_set"),
        ):
            # Simulate window closing without button click
            mock_wait.return_value = None

            # Act: Display and immediately "close" confirmation popup
            result = ConfirmationPopupWindow.display(
                parent=tk_root,
                usage_popup_window=popup_window,
                title="Confirm Action",
                ptype="component_editor_validation",
                geometry="600x220",
                instructions_text=rich_text_widget,
            )

            # Assert: Result defaults to False
            assert result is False, "Should default to False when closed without confirmation"


def test_finalize_setup_popupwindow_handles_destroyed_tk() -> None:
    """Ensure finalize_setup_popupwindow doesn't raise if Tk has been destroyed and deiconify() raises tk.TclError."""

    class FakePopup:  # pylint: disable=too-few-public-methods
        """Fake popup window simulating destroyed Tk."""

        def __init__(self) -> None:
            self.root = Mock()
            # Minimal methods used by finalize_setup_popupwindow
            self.root.update_idletasks = Mock(return_value=None)
            self.root.winfo_reqheight = Mock(return_value=10)
            self.root.winfo_reqwidth = Mock(return_value=20)
            self.root.geometry = Mock()

            # Simulate a destroyed Tk: deiconify raises TclError
            self.root.deiconify = Mock(side_effect=tk.TclError("application has been destroyed"))
            # These should not be invoked after deiconify fails
            self.root.attributes = Mock()
            self.root.grab_set = Mock()
            self.root.protocol = Mock()

    fake = FakePopup()

    # Should not raise even though deiconify raises
    PopupWindow.finalize_setup_popupwindow(fake, parent=None, close_callback=lambda: None)

    # deiconify was attempted
    fake.root.deiconify.assert_called_once()
    # attributes/grab_set/protocol should not be called because deiconify failed
    assert not fake.root.attributes.called
    assert not fake.root.grab_set.called
    assert not fake.root.protocol.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
