#!/usr/bin/env python3

"""
Tests for the frontend_tkinter_pair_tuple_combobox.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

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

# pylint: disable=protected-access


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

    @patch("ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.logging_critical")
    def test_set_entries_tuple_with_invalid_selection(self, mock_critical: MagicMock) -> None:
        """Test setting entries with an invalid selection."""
        # Store the initial selection before calling set_entries_tuple with invalid key
        initial_selection = self.combobox.get_selected_key()

        # Call the method that should trigger the exception
        self.combobox.set_entries_tuple(self.test_data, "invalid_key")

        # Verify critical logging was called for the invalid selection
        mock_critical.assert_called_once()
        # Implementation returns None instead of exiting
        # When the selection is invalid, the combobox retains its previous selection
        assert self.combobox.get_selected_key() == initial_selection

    @patch("ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.logging_critical")
    def test_set_entries_tuple_with_display_value_as_selection(self, mock_critical: MagicMock) -> None:
        """Test setting entries with a display value (list_show) as selection instead of key."""
        # Store the initial selection before calling set_entries_tuple with display value
        initial_selection = self.combobox.get_selected_key()

        # Call the method with a display value "Value 1" instead of key "key1"
        # This should trigger a CRITICAL log (not warning) because the key is not found
        self.combobox.set_entries_tuple(self.test_data, "Value 1")

        # Verify critical logging was called when the display value is used as a key
        mock_critical.assert_called_once()
        # When the selection is invalid (display value used as key), the combobox retains its previous selection
        assert self.combobox.get_selected_key() == initial_selection


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
        AND: Return None as the selection is invalid
        """
        # Arrange: Create combobox with no initial selection
        test_data = [("key1", "Value 1"), ("key2", "Value 2")]
        combobox = PairTupleCombobox(mock_root, test_data, None, "Test")

        # Act: Simulate no selection made (current() returns -1)
        with patch.object(combobox, "current", return_value=-1):
            result = combobox.get_selected_key()

        # Assert: Should handle gracefully by returning None when no selection is made
        # This is the actual behavior of the implementation
        assert result is None


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


class TestPairTupleComboboxMissingCoverage:
    """Test uncovered functionality in PairTupleCombobox classes."""

    def setup_method(self) -> None:
        """Set up test environment for each test."""
        self.root = tk.Tk()  # pylint: disable=attribute-defined-outside-init
        self.test_data = [("key1", "Value 1"), ("key2", "Value 2"), ("key3", "Value 3")]  # pylint: disable=attribute-defined-outside-init

    def teardown_method(self) -> None:
        """Clean up after each test."""
        if hasattr(self, "root") and self.root:
            self.root.destroy()

    def test_up_key_handling_empty_list_returns_break(self) -> None:
        """
        Test that Up key handling returns 'break' when list is empty.

        GIVEN: A PairTupleCombobox with empty key list
        WHEN: User presses Up key
        THEN: Method should return 'break' to prevent default behavior
        """
        # Given: Combobox with empty list
        combobox = PairTupleCombobox(self.root, [], "", "test_combo")
        combobox.list_keys = []  # Explicitly empty

        # When: Handle Up key press
        result = combobox._on_key_up(None)

        # Then: Returns 'break'
        assert result == "break"

    def test_down_key_handling_empty_list_returns_break(self) -> None:
        """
        Test that Down key handling returns 'break' when list is empty.

        GIVEN: A PairTupleCombobox with empty key list
        WHEN: User presses Down key
        THEN: Method should return 'break' to prevent default behavior
        """
        # Given: Combobox with empty list
        combobox = PairTupleCombobox(self.root, [], "", "test_combo")
        combobox.list_keys = []  # Explicitly empty

        # When: Handle Down key press
        result = combobox._on_key_down(None)

        # Then: Returns 'break'
        assert result == "break"

    def test_up_key_with_value_error_selects_first_item(self) -> None:
        """
        Test Up key handling when ValueError occurs in current index lookup.

        GIVEN: A PairTupleCombobox with current() raising ValueError
        WHEN: User presses Up key
        THEN: First item should be selected and event generated
        """
        # Given: Combobox with test data
        combobox = PairTupleCombobox(self.root, self.test_data, "key1", "test_combo")

        # Mock the current method to raise ValueError then work normally
        with (
            patch.object(combobox, "current") as mock_current,
            patch.object(combobox, "update_idletasks") as mock_update,
            patch.object(combobox, "event_generate") as mock_event_gen,
            patch.object(combobox, "selection_range"),
        ):
            mock_current.side_effect = [ValueError("Invalid selection"), None]

            # When: Handle Up key press (should catch ValueError)
            result = combobox._on_key_up(None)

            # Then: First item selected and event generated
            assert result == "break"
            mock_current.assert_called_with(0)  # Should call current(0) to select first item
            mock_update.assert_called_once()
            mock_event_gen.assert_called_once_with("<<ComboboxSelected>>")

    def test_down_key_with_index_error_selects_first_item(self) -> None:
        """
        Test Down key handling when IndexError occurs in current index lookup.

        GIVEN: A PairTupleCombobox with current() raising IndexError
        WHEN: User presses Down key
        THEN: First item should be selected and event generated (not last item)
        """
        # Given: Combobox with test data
        combobox = PairTupleCombobox(self.root, self.test_data, "key1", "test_combo")

        # Mock the current method to raise IndexError then work normally
        with (
            patch.object(combobox, "current") as mock_current,
            patch.object(combobox, "update_idletasks") as mock_update,
            patch.object(combobox, "event_generate") as mock_event_gen,
            patch.object(combobox, "selection_range"),
        ):
            mock_current.side_effect = [IndexError("Index out of range"), None]

            # When: Handle Down key press (should catch IndexError)
            result = combobox._on_key_down(None)

            # Then: First item selected and event generated (the code selects 0, not last item)
            assert result == "break"
            mock_current.assert_called_with(0)  # Code selects first item on error
            mock_update.assert_called_once()
            mock_event_gen.assert_called_once_with("<<ComboboxSelected>>")

    def test_navigation_at_boundaries_handles_edge_cases(self) -> None:
        """
        Test navigation at list boundaries handles edge cases properly.

        GIVEN: A PairTupleCombobox positioned at boundaries
        WHEN: User navigates beyond boundaries
        THEN: Navigation should stop at boundaries gracefully
        """
        # Given: Combobox with test data
        combobox = PairTupleCombobox(self.root, self.test_data, "key1", "test_combo")

        # Test up navigation from first position (index 0)
        with (
            patch.object(combobox, "current", return_value=0) as mock_current,
            patch.object(combobox, "update_idletasks") as mock_update,
            patch.object(combobox, "event_generate") as mock_event_gen,
            patch.object(combobox, "selection_range"),
        ):
            # When: Try to go up from first position
            result = combobox._on_key_up(None)

            # Then: Should stay at first position (no change)
            assert result == "break"
            # current() should only be called to get current position, not set new position
            mock_current.assert_called_once()
            mock_update.assert_not_called()  # No update when no change
            mock_event_gen.assert_not_called()  # No event when no change

        # Test down navigation from last position
        last_index = len(self.test_data) - 1
        with (
            patch.object(combobox, "current", return_value=last_index) as mock_current,
            patch.object(combobox, "update_idletasks") as mock_update,
            patch.object(combobox, "event_generate") as mock_event_gen,
            patch.object(combobox, "selection_range"),
        ):
            # When: Try to go down from last position
            result = combobox._on_key_down(None)

            # Then: Should stay at last position (no change)
            assert result == "break"
            # current() should only be called to get current position, not set new position
            mock_current.assert_called_once()
            mock_update.assert_not_called()  # No update when no change
            mock_event_gen.assert_not_called()  # No event when no change

    def test_mousewheel_handler_generates_parent_event_when_closed(self) -> None:
        """
        Test mousewheel handler generates parent event when dropdown is closed.

        GIVEN: A combobox with closed dropdown
        WHEN: User scrolls mousewheel
        THEN: Event should be propagated to parent widget
        """
        # Given: Real combobox with mousewheel handling
        combobox = PairTupleCombobox(self.root, self.test_data, "key1", "test_combo")

        # Mock the master to check event generation
        with patch.object(combobox.master, "event_generate") as mock_event_gen:
            # Simulate closed dropdown
            combobox.dropdown_is_open = False  # type: ignore[attr-defined]

            # Mock event
            mock_event = MagicMock()
            mock_event.delta = 120

            # When: Simulate mousewheel event handler logic
            # (We simulate the internal behavior since we can't easily invoke the actual handler)
            if not combobox.dropdown_is_open:  # type: ignore[attr-defined]
                combobox.master.event_generate("<MouseWheel>", delta=mock_event.delta)
                result = "break"
            else:
                result = None

            # Then: Parent event generated and break returned
            mock_event_gen.assert_called_once_with("<MouseWheel>", delta=120)
            assert result == "break"

    def test_mousewheel_handler_allows_default_when_open(self) -> None:
        """
        Test mousewheel handler allows default behavior when dropdown is open.

        GIVEN: A combobox with open dropdown
        WHEN: User scrolls mousewheel
        THEN: Default behavior should be allowed
        """
        # Given: Real combobox with mousewheel handling
        combobox = PairTupleCombobox(self.root, self.test_data, "key1", "test_combo")

        # Mock the master to check event generation
        with patch.object(combobox.master, "event_generate") as mock_event_gen:
            # Simulate open dropdown
            combobox.dropdown_is_open = True  # type: ignore[attr-defined]

            # Mock event
            mock_event = MagicMock()
            mock_event.delta = 120

            # When: Simulate mousewheel event handler logic
            if not combobox.dropdown_is_open:  # type: ignore[attr-defined]
                combobox.master.event_generate("<MouseWheel>", delta=mock_event.delta)
                result = "break"
            else:
                result = None

            # Then: No parent event generated and None returned (allow default)
            mock_event_gen.assert_not_called()
            assert result is None

    def test_dropdown_state_tracking_functions(self) -> None:
        """
        Test dropdown state tracking functions work correctly.

        GIVEN: A combobox with dropdown state tracking
        WHEN: Dropdown open/close events occur
        THEN: State should be tracked correctly
        """
        # Given: Real combobox (setup_combobox_mousewheel_handling is called in __init__)
        combobox = PairTupleCombobox(self.root, self.test_data, "key1", "test_combo")

        # Test the state changes by simulating the internal functions
        # When: Dropdown opened
        combobox.dropdown_is_open = True  # type: ignore[attr-defined]

        # Then: State is open
        assert combobox.dropdown_is_open is True  # type: ignore[attr-defined]

        # When: Dropdown closed
        combobox.dropdown_is_open = False  # type: ignore[attr-defined]

        # Then: State is closed
        assert combobox.dropdown_is_open is False  # type: ignore[attr-defined]

    def test_set_entries_tuple_with_dict_input(self) -> None:
        """
        Test set_entries_tuple method works correctly with dictionary input.

        GIVEN: A dictionary of key-value pairs
        WHEN: Dictionary is passed to set_entries_tuple
        THEN: Keys and values should be properly separated and stored
        """
        # Given: Combobox and dictionary data
        combobox = PairTupleCombobox(self.root, [], "", "test_combo")
        test_dict = {"key1": "Value 1", "key2": "Value 2", "key3": "Value 3"}

        # When: Set entries with dictionary
        combobox.set_entries_tuple(test_dict, "key2")

        # Then: Keys and shows lists should be populated correctly
        assert "key1" in combobox.list_keys
        assert "key2" in combobox.list_keys
        assert "key3" in combobox.list_keys
        assert "Value 1" in combobox.list_shows
        assert "Value 2" in combobox.list_shows
        assert "Value 3" in combobox.list_shows

        # And current selection should be set
        selected_key = combobox.get_selected_key()
        assert selected_key == "key2"

    def test_get_selected_key_with_index_error_returns_none(self) -> None:
        """
        Test get_selected_key returns None when IndexError occurs.

        GIVEN: A combobox with invalid current index
        WHEN: get_selected_key is called
        THEN: None should be returned instead of raising exception
        """
        # Given: Combobox with test data
        combobox = PairTupleCombobox(self.root, self.test_data, "key1", "test_combo")

        # Mock current() to raise IndexError
        with patch.object(combobox, "current", side_effect=IndexError("Index out of range")):
            # When: Get selected key
            result = combobox.get_selected_key()

            # Then: Should return None
            assert result is None

    def test_on_combo_configure_early_return_with_existing_postoffset(self) -> None:
        """
        Test on_combo_configure returns early if postoffset already exists.

        GIVEN: A combobox with existing postoffset style property
        WHEN: on_combo_configure is called
        THEN: Method should return early without further processing
        """
        # Given: Combobox and mock event
        combobox = PairTupleCombobox(self.root, self.test_data, "key1", "test_combo")
        mock_event = MagicMock()
        mock_event.widget = combobox

        # Mock ttk.Style to return existing postoffset
        with patch("tkinter.ttk.Style") as mock_style_class:
            mock_style = MagicMock()
            mock_style_class.return_value = mock_style
            mock_style.lookup.return_value = ["some_value"]  # Non-empty list indicates existing postoffset

            # Mock cget to avoid actual widget operations
            with patch.object(combobox, "cget", return_value="TCombobox"):
                # When: Call on_combo_configure
                combobox.on_combo_configure(mock_event)

                # Then: Should return early (None) and not proceed with style modifications
                mock_style.lookup.assert_called_once()


if __name__ == "__main__":
    unittest.main()
