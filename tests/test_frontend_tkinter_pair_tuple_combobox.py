#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_pair_tuple_combobox.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from tkinter import ttk
from unittest.mock import MagicMock, patch

from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import PairTupleCombobox, PairTupleComboboxTooltip


class TestPairTupleComboboxTooltip(unittest.TestCase):
    """Test class for PairTupleComboboxTooltip."""

    def setUp(self) -> None:
        """Set up test environment before each test."""
        self.root = tk.Tk()
        self.test_data = [("key1", "Value 1"), ("key2", "Value 2"), ("key3", "Value 3")]

        # Create the widget with mocked bindings
        with patch.object(PairTupleComboboxTooltip, "_bind"):
            self.combobox = PairTupleComboboxTooltip(self.root, self.test_data, "key1", "Test Combobox")

    def tearDown(self) -> None:
        """Clean up after each test."""
        if hasattr(self, "root") and self.root:
            self.root.destroy()

    def test_initialization(self) -> None:
        """Test proper initialization of PairTupleComboboxTooltip."""
        # Create a fresh instance with mocked _bind method to avoid tk errors
        with patch.object(PairTupleComboboxTooltip, "_bind"):
            combobox = PairTupleComboboxTooltip(self.root, self.test_data, "key1", "Test Combobox")

        # Verify the instance is properly initialized
        assert isinstance(combobox, PairTupleComboboxTooltip)
        assert isinstance(combobox, PairTupleCombobox)
        assert isinstance(combobox, ttk.Combobox)
        assert combobox.tooltip is None
        assert combobox.list_keys == ["key1", "key2", "key3"]
        assert combobox.list_shows == ["Value 1", "Value 2", "Value 3"]
        assert combobox.get_selected_key() == "key1"

    def test_create_tooltip(self) -> None:
        """Test tooltip creation."""
        # First properly mock the tooltip attribute
        self.combobox.tooltip = None

        # Use patch where the module actually imports Toplevel
        with patch("ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.Toplevel") as mock_toplevel:
            # Setup mock for Toplevel
            mock_toplevel_instance = MagicMock()
            mock_toplevel.return_value = mock_toplevel_instance
            mock_toplevel_instance.winfo_exists.return_value = True

            # Create tooltip
            self.combobox.create_tooltip("Test tooltip")

            # Verify Toplevel was created and configured properly
            mock_toplevel.assert_called_once()
            mock_toplevel_instance.wm_overrideredirect.assert_called_once_with(boolean=True)
            mock_toplevel_instance.wm_geometry.assert_called_once()

    def test_create_tooltip_from_index_valid(self) -> None:
        """Test tooltip creation from a valid index."""
        with patch.object(self.combobox, "create_tooltip") as mock_create_tooltip:
            self.combobox.create_tooltip_from_index(0)
            mock_create_tooltip.assert_called_once_with("key1: Value 1")

    def test_create_tooltip_from_index_invalid(self) -> None:
        """Test tooltip creation from an invalid index."""
        with patch.object(self.combobox, "create_tooltip") as mock_create_tooltip:
            # This should not throw any error due to contextlib.suppress
            self.combobox.create_tooltip_from_index(99)
            mock_create_tooltip.assert_not_called()

    def test_destroy_tooltip_with_existing_tooltip(self) -> None:
        """Test destroying an existing tooltip."""
        # Create a proper mock tooltip that passes the existence check
        mock_tooltip = MagicMock()
        mock_tooltip.winfo_exists.return_value = True
        self.combobox.tooltip = mock_tooltip

        # Call destroy_tooltip
        self.combobox.destroy_tooltip()

        # Verify tooltip was destroyed
        mock_tooltip.destroy.assert_called_once()
        assert self.combobox.tooltip is None

    def test_destroy_tooltip_with_no_tooltip(self) -> None:
        """Test destroying when no tooltip exists."""
        # Ensure no tooltip exists
        self.combobox.tooltip = None

        # Call destroy_tooltip
        self.combobox.destroy_tooltip()

        # No exception should be raised and tooltip should still be None
        assert self.combobox.tooltip is None

    def test_on_combobox_selected(self) -> None:
        """Test tooltip destruction when an item is selected."""
        with patch.object(self.combobox, "destroy_tooltip") as mock_destroy_tooltip:
            self.combobox.on_combobox_selected(None)
            mock_destroy_tooltip.assert_called_once()

    def test_on_escape_press(self) -> None:
        """Test tooltip destruction when escape is pressed."""
        with patch.object(self.combobox, "destroy_tooltip") as mock_destroy_tooltip:
            self.combobox.on_escape_press(None)
            mock_destroy_tooltip.assert_called_once()

    def test_on_key_release(self) -> None:
        """Test tooltip update on key release."""
        # Mock the combobox's tk.call method
        self.combobox.tk = MagicMock()
        self.combobox.tk.call.side_effect = lambda *args: ["0"] if "curselection" in args else "dummy_pd"

        with patch.object(self.combobox, "create_tooltip_from_index") as mock_create_tooltip:
            self.combobox.on_key_release(None)
            mock_create_tooltip.assert_called_once_with(0)

    def test_on_motion(self) -> None:
        """Test tooltip update on mouse motion."""
        # Mock the combobox's tk.call method
        self.combobox.tk = MagicMock()
        self.combobox.tk.call.side_effect = lambda *args: "1" if "index" in args else "dummy_pd"

        # Create a mock event with x, y coordinates
        mock_event = MagicMock()
        mock_event.x = 10
        mock_event.y = 20

        with patch.object(self.combobox, "create_tooltip_from_index") as mock_create_tooltip:
            self.combobox.on_motion(mock_event)
            mock_create_tooltip.assert_called_once_with(1)

    def test_create_tooltip_handles_tcl_error(self) -> None:
        """Test that create_tooltip handles TclError gracefully."""
        with patch("tkinter.Toplevel", side_effect=tk.TclError("Test error")):
            # Should not raise an exception
            self.combobox.create_tooltip("Test text")
            # No assertion needed - we're just checking that no exception is raised

    def test_on_combo_configure_with_existing_postoffset(self) -> None:
        """Test that on_combo_configure returns early when postoffset exists."""
        # Create a mock event with widget
        mock_event = MagicMock()
        mock_event.widget = self.combobox

        # Mock style with existing postoffset
        mock_style = MagicMock()
        mock_style.lookup.return_value = ["some_value"]  # Non-empty result

        with patch("ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.ttk.Style", return_value=mock_style):
            # Call the method
            self.combobox.on_combo_configure(mock_event)

            # Verify lookup was called but not configure
            mock_style.lookup.assert_called_once()
            mock_style.configure.assert_not_called()

    def test_on_combo_configure_with_empty_values(self) -> None:
        """Test that on_combo_configure returns early when no values exist."""
        # Create a mock event with widget
        mock_event = MagicMock()
        mock_event.widget = self.combobox

        # Mock style with no postoffset
        mock_style = MagicMock()
        mock_style.lookup.return_value = []  # Empty result

        # Set empty values
        original_values = self.combobox["values"]
        self.combobox["values"] = ()

        with patch("ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.ttk.Style", return_value=mock_style):
            # Call the method
            self.combobox.on_combo_configure(mock_event)

            # Verify lookup was called but not configure
            mock_style.lookup.assert_called_once()
            mock_style.configure.assert_not_called()

        # Restore original values
        self.combobox["values"] = original_values

    def test_on_combo_configure_no_width_adjustment_needed(self) -> None:
        """Test that on_combo_configure returns when no width adjustment is needed."""
        # Create a mock event with widget and width
        mock_event = MagicMock()
        mock_event.widget = self.combobox
        mock_event.width = 1000  # Large width so no adjustment needed

        # Mock style with no postoffset
        mock_style = MagicMock()
        mock_style.lookup.return_value = []

        # Mock font measurement to be smaller than event width
        mock_font = MagicMock()
        mock_font.measure.return_value = 100  # Small value compared to event.width

        with (
            patch("ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.ttk.Style", return_value=mock_style),
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.tkfont.nametofont",
                return_value=mock_font,
            ),
        ):
            # Call the method
            self.combobox.on_combo_configure(mock_event)

            # Verify lookup was called but not configure
            mock_style.lookup.assert_called_once()
            mock_style.configure.assert_not_called()
            mock_font.measure.assert_called_once()

    def test_on_combo_configure_applies_style(self) -> None:
        """Test that on_combo_configure applies a new style when width adjustment is needed."""
        # Create a mock event with widget and width
        mock_event = MagicMock()
        mock_event.widget = self.combobox
        mock_event.width = 50  # Small width to force adjustment

        # Mock style with no postoffset
        mock_style = MagicMock()
        mock_style.lookup.return_value = []

        # Mock widget ID for unique style name
        self.combobox.winfo_id = MagicMock(return_value=12345)
        # Mock current combo style
        self.combobox.cget = MagicMock(
            side_effect=lambda arg: "TCombobox"
            if arg == "style"
            else ("Value 1", "Value 2", "Value 3")
            if arg == "values"
            else None
        )

        # Mock the configure method on the combobox
        original_configure = self.combobox.configure
        self.combobox.configure = MagicMock()

        # Mock font measurement to be larger than event width
        mock_font = MagicMock()
        mock_font.measure.return_value = 200  # Large value compared to event.width

        try:
            with (
                patch(
                    "ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.ttk.Style", return_value=mock_style
                ),
                patch(
                    "ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.tkfont.nametofont",
                    return_value=mock_font,
                ),
            ):
                # Call the method
                self.combobox.on_combo_configure(mock_event)

                # Verify style was configured and applied to widget
                mock_style.lookup.assert_called_once()
                mock_style.configure.assert_called_once()

                # Get the call arguments correctly
                args, kwargs = mock_style.configure.call_args
                # The first arg should be the style name
                assert args[0] == "Combobox12345.TCombobox"
                # The postoffset should be in the kwargs
                assert "postoffset" in kwargs
                assert kwargs["postoffset"] == (0, 0, 150, 0)  # Width should be 200 - 50 = 150

                # Verify configure was called on the combobox
                self.combobox.configure.assert_called_once()
                # Verify it was called with the style name
                self.combobox.configure.assert_called_once_with(style="Combobox12345.TCombobox")
        finally:
            # Restore the original configure method
            self.combobox.configure = original_configure


class TestPairTupleCombobox(unittest.TestCase):
    """Test class for PairTupleCombobox."""

    def setUp(self) -> None:
        """Set up test environment before each test."""
        self.root = tk.Tk()
        self.test_data = [("key1", "Value 1"), ("key2", "Value 2"), ("key3", "Value 3")]
        self.combobox = PairTupleCombobox(self.root, self.test_data, "key1", "Test Combobox")

    def tearDown(self) -> None:
        """Clean up after each test."""
        if hasattr(self, "root") and self.root:
            self.root.destroy()

    def test_get_selected_key(self) -> None:
        """Test getting the selected key."""
        # Initially key1 is selected
        assert self.combobox.get_selected_key() == "key1"

        # Change selection
        self.combobox.current(1)
        assert self.combobox.get_selected_key() == "key2"

    def test_get_selected_key_with_no_selection(self) -> None:
        """Test getting the selected key when nothing is selected."""
        # Create a combobox with no selection and empty list
        with patch.object(PairTupleCombobox, "_bind", return_value=None):  # Avoid tk errors
            empty_combobox = PairTupleCombobox(self.root, [], None, "Empty Combobox")

        # Patch the current method to return an index that will cause IndexError
        with patch.object(empty_combobox, "current", return_value=-1):
            assert empty_combobox.get_selected_key() is None

    def test_set_entries_tuple_with_list(self) -> None:
        """Test setting entries with a list of tuples."""
        # Create a new combobox to start with empty lists
        combobox = PairTupleCombobox(self.root, [], None, "Test Combobox")

        # Clear the lists to ensure we're starting fresh
        combobox.list_keys = []
        combobox.list_shows = []

        new_data = [("a", "A"), ("b", "B")]
        combobox.set_entries_tuple(new_data, "a")

        assert combobox.list_keys == ["a", "b"]
        assert combobox.list_shows == ["A", "B"]
        assert combobox.get() == "A"  # Check the displayed value

    def test_set_entries_tuple_with_dict(self) -> None:
        """Test setting entries with a dictionary."""
        new_data = {"a": "A", "b": "B"}
        self.combobox.set_entries_tuple(new_data, "a")

        assert "a" in self.combobox.list_keys
        assert "b" in self.combobox.list_keys
        assert "A" in self.combobox.list_shows
        assert "B" in self.combobox.list_shows
        assert self.combobox.get_selected_key() == "a"

    @patch("ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.sys_exit")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.logging_critical")
    def test_set_entries_tuple_with_invalid_type(self, mock_critical, mock_exit) -> None:
        """Test setting entries with an invalid type."""
        # Call the method that should trigger the exception
        self.combobox.set_entries_tuple("invalid", None)

        # Verify the expected logging and exit calls were made
        mock_critical.assert_called_once()
        mock_exit.assert_called_once_with(1)

    @patch("ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.sys_exit")
    @patch("ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.logging_critical")
    def test_set_entries_tuple_with_invalid_selection(self, mock_critical, mock_exit) -> None:
        """Test setting entries with an invalid selection."""
        # Call the method that should trigger the exception
        self.combobox.set_entries_tuple(self.test_data, "invalid_key")

        # Verify the expected logging and exit calls were made
        mock_critical.assert_called_once()
        mock_exit.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
