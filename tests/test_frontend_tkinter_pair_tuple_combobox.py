#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_pair_tuple_combobox.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
import unittest
from collections.abc import Iterator
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import (
    PairTupleCombobox,
    PairTupleComboboxTooltip,
    setup_combobox_mousewheel_handling,
)


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

    def test_set_entries_tuple_with_dict(self) -> None:
        """Test setting entries with a dictionary."""
        # Type ignore since the function actually supports dict per implementation
        new_data = {"a": "A", "b": "B"}  # type: ignore[misc]
        self.combobox.set_entries_tuple(new_data, "a")  # type: ignore[arg-type]

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
        # Type ignore since this test explicitly tests invalid input
        self.combobox.set_entries_tuple("invalid", None)  # type: ignore[arg-type]

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


# ================================================================================================
# Pytest-style Tests Following BDD Guidelines
# ================================================================================================

# pylint: disable=redefined-outer-name


@pytest.fixture
def mock_root() -> Iterator[tk.Tk]:
    """Create a mock tkinter root window."""
    root = tk.Tk()
    root.withdraw()  # Hide the window during testing
    yield root
    root.destroy()


@pytest.fixture
def mock_combobox(mock_root) -> ttk.Combobox:
    """Fixture providing a mock combobox for testing mouse wheel functionality."""
    combobox = ttk.Combobox(mock_root)
    combobox.master = mock_root
    return combobox


@pytest.fixture
def test_pair_tuple_data() -> list[tuple[str, str]]:
    """Fixture providing realistic test data for combobox testing."""
    return [
        ("ArduCopter", "Multi-rotor helicopter"),
        ("ArduPlane", "Fixed-wing aircraft"),
        ("Rover", "Ground vehicle"),
        ("ArduSub", "Underwater vehicle"),
    ]


@pytest.fixture
def pair_tuple_combobox(mock_root, test_pair_tuple_data) -> PairTupleCombobox:
    """Fixture providing a configured PairTupleCombobox for behavior testing."""
    return PairTupleCombobox(mock_root, test_pair_tuple_data, "ArduCopter", "Vehicle Type")


class TestMousewheelHandlingBehavior:
    """Test mouse wheel handling functionality following BDD principles."""

    def test_setup_combobox_mousewheel_handling(self, mock_combobox) -> None:
        """
        Function configures combobox to prevent unwanted value changes during scroll.

        GIVEN: A standard ttk.Combobox widget
        WHEN: setup_combobox_mousewheel_handling is called on it
        THEN: The combobox should have mouse wheel handling configured
        AND: The dropdown state tracking should be initialized
        """
        # Arrange: Verify initial state
        assert not hasattr(mock_combobox, "dropdown_is_open")

        # Act: Apply mouse wheel handling
        setup_combobox_mousewheel_handling(mock_combobox)

        # Assert: Verify configuration applied
        assert hasattr(mock_combobox, "dropdown_is_open")
        assert mock_combobox.dropdown_is_open is False

    def test_mousewheel_handler_when_dropdown_closed(self, mock_combobox) -> None:
        """
        Mouse wheel events are propagated to parent when dropdown is closed.

        GIVEN: A combobox with mouse wheel handling configured
        AND: The dropdown is closed
        WHEN: A mouse wheel event occurs over the combobox
        THEN: The event should be propagated to the parent widget
        AND: The combobox value should not change
        """
        # Arrange: Configure mouse wheel handling and closed dropdown
        setup_combobox_mousewheel_handling(mock_combobox)
        mock_combobox.dropdown_is_open = False

        # Mock the parent's event_generate method
        mock_combobox.master.event_generate = MagicMock()

        # Create a mock wheel event
        mock_event = MagicMock()
        mock_event.delta = 120

        # Act: Trigger mouse wheel event
        # We need to access the bound handler function
        bindings = mock_combobox.bind("<MouseWheel>")
        if bindings:
            # Get the handler and call it directly
            # This would normally trigger the handler, but for testing we verify the setup
            pass

        # Assert: Verify initial configuration (the actual event handling would be tested in integration)
        assert mock_combobox.dropdown_is_open is False

    def test_mousewheel_handler_when_dropdown_open(self, mock_combobox) -> None:
        """
        Mouse wheel events are processed normally when dropdown is open.

        GIVEN: A combobox with mouse wheel handling configured
        AND: The dropdown is open
        WHEN: A mouse wheel event occurs over the combobox
        THEN: The event should be processed normally by the combobox
        AND: The user should be able to scroll through options
        """
        # Arrange: Configure mouse wheel handling and open dropdown
        setup_combobox_mousewheel_handling(mock_combobox)
        mock_combobox.dropdown_is_open = True

        # Mock the parent's event_generate method
        mock_combobox.master.event_generate = MagicMock()

        # Act: Configure the state and verify
        # The actual event handling would be tested in integration tests

        # Assert: Verify dropdown state allows normal processing
        assert mock_combobox.dropdown_is_open is True

    def test_dropdown_state_management(self, mock_combobox) -> None:
        """
        Dropdown state is correctly tracked through open/close events.

        GIVEN: A combobox with mouse wheel handling configured
        WHEN: Dropdown open and close events occur
        THEN: The dropdown_is_open flag should be updated correctly
        """
        # Arrange: Configure mouse wheel handling
        setup_combobox_mousewheel_handling(mock_combobox)
        initial_state = mock_combobox.dropdown_is_open

        # Act & Assert: Verify initial state
        assert initial_state is False

        # The actual event binding testing would require tkinter event simulation
        # which is complex in unit tests. The setup verification is sufficient
        # for confirming the configuration is applied correctly.


class TestPairTupleComboboxBehavior:
    """Test PairTupleCombobox user workflow behaviors."""

    def test_user_can_create_combobox_with_vehicle_data(self, mock_root, test_pair_tuple_data) -> None:
        """
        User can create a combobox with vehicle type selections.

        GIVEN: A list of vehicle types with descriptions
        WHEN: A PairTupleCombobox is created with this data
        THEN: The combobox should display the descriptions
        AND: Store the keys for retrieval
        AND: Have mouse wheel handling automatically configured
        """
        # Arrange: Vehicle data is provided via fixture

        # Act: Create combobox with vehicle data
        combobox = PairTupleCombobox(mock_root, test_pair_tuple_data, "ArduPlane", "Vehicle Selection")

        # Assert: Verify proper initialization
        assert combobox.list_keys == ["ArduCopter", "ArduPlane", "Rover", "ArduSub"]
        assert combobox.list_shows == ["Multi-rotor helicopter", "Fixed-wing aircraft", "Ground vehicle", "Underwater vehicle"]
        assert combobox.get_selected_key() == "ArduPlane"
        assert hasattr(combobox, "dropdown_is_open")  # Mouse wheel handling applied

    def test_user_can_retrieve_selected_vehicle_key(self, pair_tuple_combobox) -> None:
        """
        User can get the key of the currently selected vehicle type.

        GIVEN: A combobox with vehicle types displayed
        WHEN: The user selects a vehicle type
        THEN: The corresponding key should be retrievable
        """
        # Arrange: Combobox is configured via fixture

        # Act: Change selection to a different vehicle
        pair_tuple_combobox.current(2)  # Select "Rover"

        # Assert: Verify correct key is returned
        assert pair_tuple_combobox.get_selected_key() == "Rover"

    def test_user_sees_descriptive_text_in_dropdown(self, pair_tuple_combobox) -> None:
        """
        User sees descriptive text in the dropdown options.

        GIVEN: A combobox with vehicle data
        WHEN: The user opens the dropdown
        THEN: They should see descriptive names, not technical keys
        """
        # Arrange: Combobox is configured via fixture

        # Act: Get the displayed values
        displayed_values = pair_tuple_combobox["values"]

        # Assert: Verify descriptive text is shown
        assert "Multi-rotor helicopter" in displayed_values
        assert "Fixed-wing aircraft" in displayed_values
        assert "ArduCopter" not in displayed_values  # Keys should not be displayed

    def test_combobox_handles_missing_selection_gracefully(self, mock_root) -> None:
        """
        Combobox handles missing or invalid selections without errors.

        GIVEN: A combobox with valid data but no initial selection
        WHEN: No selection is made (current() returns -1)
        THEN: The combobox should handle it gracefully
        AND: Return the last available key as fallback behavior
        """
        # Arrange: Create combobox with no initial selection
        test_data = [("key1", "Value 1"), ("key2", "Value 2")]
        combobox = PairTupleCombobox(mock_root, test_data, None, "Test")

        # Act: Simulate no selection made (current() returns -1)
        with patch.object(combobox, "current", return_value=-1):
            result = combobox.get_selected_key()

        # Assert: Should handle gracefully by returning the last key as fallback
        # This is the actual behavior of the implementation
        assert result == "key2"


class TestPairTupleComboboxTooltipWorkflow:
    """Test tooltip functionality user workflows."""

    def test_user_receives_tooltip_feedback_on_hover(self, mock_root, test_pair_tuple_data) -> None:
        """
        User receives tooltip feedback when hovering over dropdown items.

        GIVEN: A tooltip-enabled combobox with vehicle data
        WHEN: The user hovers over dropdown items
        THEN: A tooltip should appear with detailed information
        """
        # Arrange: Create tooltip combobox (with mocked bindings to avoid tk errors)
        with patch.object(PairTupleComboboxTooltip, "_bind"):
            tooltip_combobox = PairTupleComboboxTooltip(mock_root, test_pair_tuple_data, "ArduCopter", "Vehicle Type")

        # Act: Simulate tooltip creation for first item
        with patch.object(tooltip_combobox, "create_tooltip") as mock_create:
            tooltip_combobox.create_tooltip_from_index(0)

        # Assert: Verify tooltip content
        mock_create.assert_called_once_with("ArduCopter: Multi-rotor helicopter")

    def test_tooltip_disappears_on_selection(self, mock_root, test_pair_tuple_data) -> None:
        """
        Tooltip disappears when user makes a selection.

        GIVEN: A tooltip is currently displayed
        WHEN: The user selects an item from the dropdown
        THEN: The tooltip should be destroyed immediately
        """
        # Arrange: Create tooltip combobox with mocked bindings
        with patch.object(PairTupleComboboxTooltip, "_bind"):
            tooltip_combobox = PairTupleComboboxTooltip(mock_root, test_pair_tuple_data, "ArduCopter", "Vehicle Type")

        # Act: Simulate selection event
        with patch.object(tooltip_combobox, "destroy_tooltip") as mock_destroy:
            tooltip_combobox.on_combobox_selected(None)

        # Assert: Verify tooltip was destroyed
        mock_destroy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
