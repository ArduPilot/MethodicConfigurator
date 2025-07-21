#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_autoresize_combobox.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from unittest.mock import patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox import AutoResizeCombobox, update_combobox_width

# pylint: disable=redefined-outer-name


@pytest.fixture
def test_combobox(root: tk.Tk) -> ttk.Combobox:
    """Create a test combobox for width testing."""
    frame = ttk.Frame(root)
    frame.pack()
    return ttk.Combobox(frame)


class TestUpdateComboboxWidth:
    """Test cases for the update_combobox_width function."""

    def test_combobox_width_adjusts_to_longest_value(self, test_combobox: ttk.Combobox) -> None:
        """
        Combobox width adjusts automatically to accommodate the longest value.

        GIVEN: A combobox with values of different lengths
        WHEN: The update_combobox_width function is called
        THEN: The width should be set to accommodate the longest value
        """
        # Arrange (Given): Set combobox values with different lengths
        test_combobox["values"] = ["short", "longer", "longest"]

        # Act (When): Update the combobox width
        update_combobox_width(test_combobox)

        # Assert (Then): Width should accommodate longest value (7 characters)
        assert test_combobox.cget("width") == 7

    def test_combobox_uses_minimum_width_when_values_empty(self, test_combobox: ttk.Combobox) -> None:
        """
        Combobox uses minimum width when no values are present.

        GIVEN: A combobox with no values
        WHEN: The update_combobox_width function is called
        THEN: The width should be set to the minimum value (4)
        """
        # Arrange (Given): Set empty values
        test_combobox["values"] = []

        # Act (When): Update the combobox width
        update_combobox_width(test_combobox)

        # Assert (Then): Should use minimum width
        assert test_combobox.cget("width") == 4

    def test_combobox_uses_minimum_width_for_very_short_values(self, test_combobox: ttk.Combobox) -> None:
        """
        Combobox uses minimum width when all values are very short.

        GIVEN: A combobox with very short values
        WHEN: The update_combobox_width function is called
        THEN: The width should be set to the minimum value (4)
        """
        # Arrange (Given): Set very short values
        test_combobox["values"] = ["a", "b", "c"]

        # Act (When): Update the combobox width
        update_combobox_width(test_combobox)

        # Assert (Then): Should use minimum width
        assert test_combobox.cget("width") == 4


@pytest.fixture
def auto_resize_combobox(root: tk.Tk) -> AutoResizeCombobox:
    """Create an AutoResizeCombobox for testing."""
    frame = ttk.Frame(root)
    frame.pack()
    return AutoResizeCombobox(frame, values=["one", "two", "three"], selected_element="two", tooltip="Test Tooltip")


class TestAutoResizeCombobox:
    """Test cases for the AutoResizeCombobox class."""

    def test_user_can_see_initial_selection_in_combobox(self, auto_resize_combobox: AutoResizeCombobox) -> None:
        """
        User can see the initially selected value in the combobox.

        GIVEN: An AutoResizeCombobox with predefined values and initial selection
        WHEN: The combobox is created with "two" as selected element
        THEN: The combobox should display "two" as the current value
        """
        # Arrange (Given): AutoResizeCombobox created with initial selection
        # Act (When): Check the current value (already set during creation)
        # Assert (Then): Should display the initially selected value
        assert auto_resize_combobox.get() == "two"

    def test_user_can_update_combobox_values_and_selection(self, auto_resize_combobox: AutoResizeCombobox) -> None:
        """
        User can update both the available values and current selection.

        GIVEN: An existing AutoResizeCombobox with initial values
        WHEN: New values and selection are set using set_entries_tuple
        THEN: The combobox should reflect the new values and selection
        """
        # Arrange (Given): Existing combobox with initial values
        new_values = ["four", "five", "six"]
        new_selection = "five"

        # Act (When): Update values and selection
        auto_resize_combobox.set_entries_tuple(new_values, new_selection)

        # Assert (Then): Should display new values and selection
        assert auto_resize_combobox.get() == new_selection
        assert auto_resize_combobox["values"] == tuple(new_values)

    def test_combobox_handles_values_with_spaces_correctly(self, auto_resize_combobox: AutoResizeCombobox) -> None:
        """
        Combobox preserves values with spaces exactly as provided.

        GIVEN: Values containing various amounts of spaces
        WHEN: These values are set in the combobox
        THEN: All spaces should be preserved exactly
        """
        # Arrange (Given): Values with different space patterns
        values_with_spaces = ["option one", "option  two", "option   three"]
        selected_value = "option  two"

        # Act (When): Set values with spaces
        auto_resize_combobox.set_entries_tuple(values_with_spaces, selected_value)

        # Assert (Then): Spaces should be preserved
        assert auto_resize_combobox["values"] == tuple(values_with_spaces)
        assert auto_resize_combobox.get() == selected_value

    @patch("ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox.logging_error")
    def test_system_logs_error_when_invalid_selection_provided(
        self, mock_logging_error, auto_resize_combobox: AutoResizeCombobox
    ) -> None:
        """
        System logs an error when user provides invalid selection.

        GIVEN: A combobox with valid values
        WHEN: An invalid selection that's not in the values list is provided
        THEN: An error should be logged and the selection should remain unchanged
        """
        # Arrange (Given): Valid values and invalid selection
        valid_values = ["one", "two", "three"]
        invalid_selection = "four"
        original_value = auto_resize_combobox.get()

        # Act (When): Try to set invalid selection
        auto_resize_combobox.set_entries_tuple(valid_values, invalid_selection)

        # Assert (Then): Error logged and value unchanged
        mock_logging_error.assert_called_once()
        assert auto_resize_combobox.get() == original_value

    @patch("ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox.logging_warning")
    def test_system_logs_warning_when_no_selection_provided(
        self, mock_logging_warning, auto_resize_combobox: AutoResizeCombobox
    ) -> None:
        """
        System logs a warning when no selection is provided.

        GIVEN: A combobox with valid values
        WHEN: An empty selection is provided
        THEN: A warning should be logged
        """
        # Arrange (Given): Valid values and empty selection
        valid_values = ["one", "two", "three"]
        empty_selection = ""

        # Act (When): Set empty selection
        auto_resize_combobox.set_entries_tuple(valid_values, empty_selection)

        # Assert (Then): Warning should be logged
        mock_logging_warning.assert_called_once()

    @patch("ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox.update_combobox_width")
    def test_width_update_skipped_for_empty_values(self, mock_update_width, auto_resize_combobox: AutoResizeCombobox) -> None:
        """
        Width update is not called when values list is empty.

        GIVEN: A combobox that supports width updating
        WHEN: An empty values list is provided
        THEN: The width update function should not be called
        """
        # Arrange (Given): Empty values list
        empty_values = []

        # Act (When): Set empty values
        auto_resize_combobox.set_entries_tuple(empty_values, "")

        # Assert (Then): Width update should not be called
        mock_update_width.assert_not_called()

    @patch("ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox.show_tooltip")
    def test_tooltip_displays_when_help_text_provided(
        self, mock_show_tooltip, auto_resize_combobox: AutoResizeCombobox
    ) -> None:
        """
        Tooltip is displayed when help text is provided.

        GIVEN: A combobox that supports tooltips
        WHEN: Values are set with tooltip text provided
        THEN: The tooltip should be displayed with the help text
        """
        # Arrange (Given): Values and help text
        values = ["one", "two"]
        selection = "one"
        help_text = "Help text"

        # Act (When): Set values with tooltip
        auto_resize_combobox.set_entries_tuple(values, selection, help_text)

        # Assert (Then): Tooltip should be shown
        mock_show_tooltip.assert_called_once_with(auto_resize_combobox, help_text)

    @patch("ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox.show_tooltip")
    def test_tooltip_not_displayed_when_no_help_text(
        self, mock_show_tooltip, auto_resize_combobox: AutoResizeCombobox
    ) -> None:
        """
        Tooltip is not displayed when no help text is provided.

        GIVEN: A combobox that supports tooltips
        WHEN: Values are set with None as tooltip text
        THEN: The tooltip should not be displayed
        """
        # Arrange (Given): Values without help text
        values = ["one", "two"]
        selection = "one"
        no_help_text = None

        # Act (When): Set values without tooltip
        auto_resize_combobox.set_entries_tuple(values, selection, no_help_text)

        # Assert (Then): Tooltip should not be shown
        mock_show_tooltip.assert_not_called()
