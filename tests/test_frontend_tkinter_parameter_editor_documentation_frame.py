#!/usr/bin/env python3

"""
Behavior-driven tests for the DocumentationFrame GUI component.

This file tests user interactions with the documentation display in the
ArduPilot Methodic Configurator parameter editor.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from collections.abc import Generator
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame import DocumentationFrame

# pylint: disable=redefined-outer-name, unused-argument


@pytest.fixture
def mock_parameter_editor() -> MagicMock:
    """Fixture providing a mock parameter editor data model with realistic test data."""
    manager = MagicMock()

    # Set up current file
    manager.current_file = "01_initial_setup.param"

    # Mock documentation data retrieval
    def mock_get_documentation_text_and_url(key: str) -> tuple[str, str]:
        return {
            "blog": ("ArduPilot Forum Blog Post", "https://discuss.ardupilot.org/t/methodic-configurator/"),
            "wiki": ("Configuration Wiki Page", "https://ardupilot.org/copter/docs/configuring-hardware.html"),
            "external_tool": ("Mission Planner Tool", "https://ardupilot.org/planner/"),
            "mandatory": ("75", None),
        }[key]

    manager.get_documentation_text_and_url.side_effect = mock_get_documentation_text_and_url
    manager.get_documentation_frame_title.return_value = "01_initial_setup.param Documentation"
    manager.get_why_why_now_tooltip.return_value = "Why: Initial setup is required\nWhy now: Must be done first"
    manager.parse_mandatory_level_percentage.return_value = (75, "This step is 75% mandatory")

    return manager


@pytest.fixture
def documentation_frame(mock_parameter_editor) -> Generator[DocumentationFrame, None, None]:
    """Fixture providing a properly initialized DocumentationFrame for testing."""
    root = tk.Tk()
    frame = DocumentationFrame(root, mock_parameter_editor)
    yield frame
    root.destroy()


class TestDocumentationFrameInitialization:
    """Test the initial setup and creation of the documentation frame."""

    def test_user_sees_documentation_frame_with_proper_title(self, documentation_frame, mock_parameter_editor) -> None:
        """
        User sees a documentation frame with the current file's title.

        GIVEN: A user is viewing parameter configuration
        WHEN: The documentation frame is displayed
        THEN: The frame should show the current file name in the title
        """
        assert isinstance(documentation_frame.documentation_frame, ttk.LabelFrame)
        assert documentation_frame.documentation_frame.cget("text") == "01_initial_setup.param Documentation"

    def test_user_sees_all_documentation_sections_displayed(self, documentation_frame) -> None:
        """
        User sees all required documentation sections in the interface.

        GIVEN: A user needs to access documentation for configuration
        WHEN: The documentation frame is created
        THEN: All documentation sections should be visible
        """
        expected_labels = [
            documentation_frame.BLOG_LABEL,
            documentation_frame.WIKI_LABEL,
            documentation_frame.EXTERNAL_TOOL_LABEL,
        ]

        for label in expected_labels:
            assert label in documentation_frame.documentation_labels
            assert isinstance(documentation_frame.documentation_labels[label], ttk.Label)

        assert isinstance(documentation_frame.mandatory_level, ttk.Progressbar)


class TestDocumentationDisplayBehavior:
    """Test how documentation content is displayed to users."""

    def test_user_sees_documentation_links_with_clickable_styling(self, documentation_frame) -> None:
        """
        User sees documentation links styled as clickable elements.

        GIVEN: A user wants to access external documentation
        WHEN: Documentation links are available
        THEN: Links should be displayed in blue with hand cursor
        """
        documentation_frame.refresh_documentation_labels()

        # Check that links are styled as clickable
        blog_label = documentation_frame.documentation_labels[documentation_frame.BLOG_LABEL]
        assert str(blog_label.cget("foreground")) == "blue"
        assert str(blog_label.cget("cursor")) == "hand2"

    def test_user_sees_mandatory_level_progress_bar_with_correct_value(
        self, documentation_frame, mock_parameter_editor
    ) -> None:
        """
        User sees mandatory level displayed as a progress bar.

        GIVEN: A configuration step has a mandatory level
        WHEN: The documentation is refreshed
        THEN: The progress bar should show the correct percentage
        """
        documentation_frame.refresh_documentation_labels()

        assert documentation_frame.mandatory_level.cget("value") == 75

    @patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame.show_tooltip")
    def test_user_sees_helpful_tooltips_on_documentation_elements(self, mock_show_tooltip, documentation_frame) -> None:
        """
        User sees helpful tooltips when hovering over documentation elements.

        GIVEN: A user is unsure about documentation elements
        WHEN: They hover over labels and controls
        THEN: Helpful tooltips should be displayed
        """
        documentation_frame.refresh_documentation_labels()

        # Verify tooltips were set for documentation links
        blog_label = documentation_frame.documentation_labels[documentation_frame.BLOG_LABEL]
        mock_show_tooltip.assert_any_call(blog_label, "https://discuss.ardupilot.org/t/methodic-configurator/")

        # Verify tooltip was set for mandatory level
        mock_show_tooltip.assert_any_call(documentation_frame.mandatory_level, "This step is 75% mandatory")


class TestDocumentationInteractionBehavior:
    """Test user interactions with documentation elements."""

    @patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame.webbrowser_open_url")
    def test_user_can_click_documentation_links_to_open_in_browser(self, mock_webbrowser_open, documentation_frame) -> None:
        """
        User can click on documentation links to open them in web browser.

        GIVEN: A user wants to read external documentation
        WHEN: They click on a documentation link
        THEN: The link should open in their default web browser
        """
        documentation_frame.refresh_documentation_labels()

        # Simulate clicking on documentation links
        blog_label = documentation_frame.documentation_labels[documentation_frame.BLOG_LABEL]
        blog_label.event_generate("<Button-1>")

        wiki_label = documentation_frame.documentation_labels[documentation_frame.WIKI_LABEL]
        wiki_label.event_generate("<Button-1>")

        mock_webbrowser_open.assert_any_call("https://discuss.ardupilot.org/t/methodic-configurator/")
        mock_webbrowser_open.assert_any_call("https://ardupilot.org/copter/docs/configuring-hardware.html")

    def test_user_can_toggle_auto_open_documentation_setting(self, documentation_frame) -> None:
        """
        User can toggle the auto-open documentation setting.

        GIVEN: A user wants to control automatic documentation opening
        WHEN: They interact with the auto-open checkbox
        THEN: The setting should be updated accordingly
        """
        # Test enabling auto-open
        documentation_frame.auto_open_var.set(True)
        assert documentation_frame.get_auto_open_documentation_in_browser() is True

        # Test disabling auto-open
        documentation_frame.auto_open_var.set(False)
        assert documentation_frame.get_auto_open_documentation_in_browser() is False


class TestDocumentationUpdateBehavior:
    """Test how documentation updates when configuration changes."""

    def test_user_sees_updated_documentation_when_file_changes(self, documentation_frame, mock_parameter_editor) -> None:
        """
        User sees updated documentation when switching to different parameter file.

        GIVEN: A user switches to a different parameter file
        WHEN: The documentation frame refreshes
        THEN: The frame title and content should update accordingly
        """
        # Change the current file
        mock_parameter_editor.current_file = "02_frame_setup.param"
        mock_parameter_editor.get_documentation_frame_title.return_value = "02_frame_setup.param Documentation"

        documentation_frame.refresh_documentation_labels()

        assert documentation_frame.documentation_frame.cget("text") == "02_frame_setup.param Documentation"

    @patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame.show_tooltip")
    def test_user_sees_why_why_now_explanation_in_frame_tooltip(self, mock_show_tooltip, documentation_frame) -> None:
        """
        User sees why/why now explanation when hovering over the documentation frame.

        GIVEN: A user wants to understand the purpose of the current step
        WHEN: They hover over the documentation frame
        THEN: A tooltip should explain why this step is important
        """
        documentation_frame.update_why_why_now_tooltip()

        mock_show_tooltip.assert_called_once_with(
            documentation_frame.documentation_frame,
            "Why: Initial setup is required\nWhy now: Must be done first",
            position_below=False,
        )


class TestDocumentationEdgeCases:
    """Test edge cases and error handling in documentation display."""

    def test_user_sees_fallback_when_no_documentation_links_available(
        self, documentation_frame, mock_parameter_editor
    ) -> None:
        """
        User sees appropriate fallback when documentation links are unavailable.

        GIVEN: Some documentation links are not available
        WHEN: The documentation is refreshed
        THEN: Non-clickable text should be displayed appropriately
        """
        # Mock no URLs available
        mock_parameter_editor.get_documentation_text_and_url.side_effect = lambda key: {
            "blog": ("Forum Discussion", None),
            "wiki": ("Wiki Page", None),
            "external_tool": ("Tool Link", None),
            "mandatory": ("0", None),
        }[key]

        documentation_frame.refresh_documentation_labels()

        # Check that labels are styled as non-clickable
        blog_label = documentation_frame.documentation_labels[documentation_frame.BLOG_LABEL]
        assert str(blog_label.cget("foreground")) == "black"
        assert str(blog_label.cget("cursor")) == "arrow"

    @patch("ardupilot_methodic_configurator.frontend_tkinter_parameter_editor_documentation_frame.show_tooltip")
    def test_user_sees_no_tooltip_when_why_why_now_not_available(
        self, mock_show_tooltip, documentation_frame, mock_parameter_editor
    ) -> None:
        """
        User sees no tooltip when why/why now explanation is not available.

        GIVEN: No why/why now explanation is available for the current step
        WHEN: The tooltip is updated
        THEN: No tooltip should be shown
        """
        mock_parameter_editor.get_why_why_now_tooltip.return_value = ""

        documentation_frame.update_why_why_now_tooltip()

        mock_show_tooltip.assert_not_called()

    def test_user_sees_zero_mandatory_level_for_optional_steps(self, documentation_frame, mock_parameter_editor) -> None:
        """
        User sees zero mandatory level for optional configuration steps.

        GIVEN: A configuration step is completely optional
        WHEN: The documentation is displayed
        THEN: The progress bar should show 0%
        """
        mock_parameter_editor.parse_mandatory_level_percentage.return_value = (0, "This step is optional")

        documentation_frame._refresh_mandatory_level("0%")  # pylint: disable=protected-access

        assert documentation_frame.mandatory_level.cget("value") == 0
