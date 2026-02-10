#!/usr/bin/env python3

"""
Data-dependent (ComponentEditorWindow) Component editor GUI tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

# Import shared test utilities to avoid code duplication
from test_frontend_tkinter_component_editor_base import (
    SharedTestArgumentParser,
    add_editor_helper_methods,
    setup_common_editor_mocks,
)

from ardupilot_methodic_configurator.frontend_tkinter_component_editor import ComponentEditorWindow
from ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox import PairTupleCombobox

# pylint: disable=protected-access,redefined-outer-name


@pytest.fixture
def editor_with_mocked_root() -> ComponentEditorWindow:
    """Create a mock ComponentEditorWindow for testing."""
    # Create the class without initialization
    with patch.object(ComponentEditorWindow, "__init__", return_value=None):
        editor = ComponentEditorWindow()  # pylint: disable=no-value-for-parameter

        # Set up common mocks using shared utility
        setup_common_editor_mocks(editor)

        # Add additional mocks specific to ComponentEditorWindow
        editor.data_model.validate_entry_limits = MagicMock(return_value=("", None))
        editor.data_model.validate_cell_voltage = MagicMock(return_value=("", None))
        editor.data_model.validate_all_data = MagicMock(return_value=(True, []))
        editor.data_model.get_combobox_values_for_path = MagicMock(return_value=())
        editor.data_model.get_component_value = MagicMock(return_value=None)

        # Don't mock add_entry_or_combobox so we can test the real implementation
        # __get__ is a method binding and not a method call, pylint gets confused, hence the disable
        editor.add_entry_or_combobox = ComponentEditorWindow.add_entry_or_combobox.__get__(editor, ComponentEditorWindow)  # pylint: disable=no-value-for-parameter

        # Add helper methods using shared utility
        add_editor_helper_methods(editor)

        yield editor


class TestComponentEditorWindow:  # pylint: disable=too-many-public-methods
    """Test cases for ComponentEditorWindow class."""

    def test_init(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test ComponentEditorWindow initialization."""
        assert hasattr(editor_with_mocked_root, "local_filesystem")
        assert hasattr(editor_with_mocked_root, "data_model")
        assert hasattr(editor_with_mocked_root, "entry_widgets")
        assert editor_with_mocked_root.version == "1.0.0"

    def test_set_vehicle_type_and_version(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test setting vehicle type and version."""
        vehicle_type = "ArduCopter"
        version = "4.6.x"

        with patch.object(editor_with_mocked_root, "set_component_value_and_update_ui") as mock_set_value:
            editor_with_mocked_root.set_vehicle_type_and_version(vehicle_type, version)

            # Should set both type and version
            assert mock_set_value.call_count == 2
            mock_set_value.assert_any_call(("Flight Controller", "Firmware", "Type"), vehicle_type)
            mock_set_value.assert_any_call(("Flight Controller", "Firmware", "Version"), version)

    def test_set_vehicle_type_and_version_no_version(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test setting vehicle type without version."""
        vehicle_type = "ArduCopter"
        version = ""

        with patch.object(editor_with_mocked_root, "set_component_value_and_update_ui") as mock_set_value:
            editor_with_mocked_root.set_vehicle_type_and_version(vehicle_type, version)

            # Should only set type, not version
            mock_set_value.assert_called_once_with(("Flight Controller", "Firmware", "Type"), vehicle_type)

    def test_set_fc_manufacturer_valid(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test setting valid flight controller manufacturer."""
        manufacturer = "Matek"

        editor_with_mocked_root.data_model.is_fc_manufacturer_valid = MagicMock(return_value=True)

        with patch.object(editor_with_mocked_root, "set_component_value_and_update_ui") as mock_set_value:
            editor_with_mocked_root.set_fc_manufacturer(manufacturer)

            editor_with_mocked_root.data_model.is_fc_manufacturer_valid.assert_called_once_with(manufacturer)
            mock_set_value.assert_called_once_with(("Flight Controller", "Product", "Manufacturer"), manufacturer)

    def test_set_fc_manufacturer_invalid(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test setting invalid flight controller manufacturer."""
        manufacturer = "InvalidManufacturer"

        editor_with_mocked_root.data_model.is_fc_manufacturer_valid = MagicMock(return_value=False)

        with patch.object(editor_with_mocked_root, "set_component_value_and_update_ui") as mock_set_value:
            editor_with_mocked_root.set_fc_manufacturer(manufacturer)

            editor_with_mocked_root.data_model.is_fc_manufacturer_valid.assert_called_once_with(manufacturer)
            mock_set_value.assert_not_called()

    def test_set_fc_model_valid(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test setting valid flight controller model."""
        model = "H743 SLIM"

        editor_with_mocked_root.data_model.is_fc_model_valid = MagicMock(return_value=True)

        with patch.object(editor_with_mocked_root, "set_component_value_and_update_ui") as mock_set_value:
            editor_with_mocked_root.set_fc_model(model)

            editor_with_mocked_root.data_model.is_fc_model_valid.assert_called_once_with(model)
            mock_set_value.assert_called_once_with(("Flight Controller", "Product", "Model"), model)

    def test_set_fc_model_invalid(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test setting invalid flight controller model."""
        model = "InvalidModel"

        editor_with_mocked_root.data_model.is_fc_model_valid = MagicMock(return_value=False)

        with patch.object(editor_with_mocked_root, "set_component_value_and_update_ui") as mock_set_value:
            editor_with_mocked_root.set_fc_model(model)

            editor_with_mocked_root.data_model.is_fc_model_valid.assert_called_once_with(model)
            mock_set_value.assert_not_called()

    def test_set_mcu_series(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test setting MCU series."""
        mcu = "STM32H7xx"

        with patch.object(editor_with_mocked_root, "set_component_value_and_update_ui") as mock_set_value:
            editor_with_mocked_root.set_mcu_series(mcu)

            mock_set_value.assert_called_once_with(("Flight Controller", "Specifications", "MCU Series"), mcu)

    def test_set_mcu_series_empty(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test setting empty MCU series."""
        mcu = ""

        with patch.object(editor_with_mocked_root, "set_component_value_and_update_ui") as mock_set_value:
            editor_with_mocked_root.set_mcu_series(mcu)

            mock_set_value.assert_not_called()

    def test_set_vehicle_configuration_template(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test setting vehicle configuration template."""
        template = "default_template"

        editor_with_mocked_root.data_model.set_configuration_template = MagicMock()
        editor_with_mocked_root.set_vehicle_configuration_template(template)

        editor_with_mocked_root.data_model.set_configuration_template.assert_called_once_with(template)

    def test_set_values_from_fc_parameters(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test processing flight controller parameters."""
        fc_parameters = {"PARAM1": 123, "PARAM2": "value"}
        doc = {"PARAM1": "Parameter 1 description"}

        editor_with_mocked_root.data_model.process_fc_parameters = MagicMock()
        editor_with_mocked_root.set_values_from_fc_parameters(fc_parameters, doc)

        editor_with_mocked_root.data_model.process_fc_parameters.assert_called_once_with(fc_parameters, doc)

    def test_update_component_protocol_combobox_entries(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test updating protocol combobox entries."""
        component_path = ("RC", "FC Connection", "Type")  # Use proper 3-level path structure
        connection_type = "PWM"
        expected_result = "test_result"

        editor_with_mocked_root.data_model.set_component_value = MagicMock()
        editor_with_mocked_root.data_model.get_combobox_values_for_path = MagicMock(return_value=("PWM", "SBUS"))

        with patch.object(
            editor_with_mocked_root, "update_protocol_combobox_entries", return_value=expected_result
        ) as mock_update:
            result = editor_with_mocked_root.update_component_protocol_combobox_entries(component_path, connection_type)

            editor_with_mocked_root.data_model.set_component_value.assert_called_once_with(component_path, connection_type)
            mock_update.assert_called_once_with(("PWM", "SBUS"), ("RC", "FC Connection", "Protocol"))
            assert result == expected_result

    def test_update_protocol_combobox_entries_with_widget(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test updating protocol combobox with existing widget."""
        protocols = ("PWM", "SBUS", "PPM")
        protocol_path = ("RC Receiver", "FC Connection", "Protocol")  # Use proper path structure

        # Create mock PairTupleCombobox
        mock_combobox = MagicMock(spec=PairTupleCombobox)
        mock_combobox.get_selected_key.return_value = "PWM"  # Current selection is valid
        mock_combobox.list_keys = list(protocols)
        editor_with_mocked_root.entry_widgets[protocol_path] = mock_combobox

        result = editor_with_mocked_root.update_protocol_combobox_entries(protocols, protocol_path)

        # Should update values and not show error
        expected_tuples = [(p, p) for p in protocols]
        mock_combobox.set_entries_tuple.assert_called_once_with(expected_tuples, "PWM")
        assert mock_combobox.get_selected_key.call_count == 1  # Called once to get current selection for validation
        assert result == ""

    def test_update_protocol_combobox_entries_invalid_selection(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test updating protocol combobox with invalid current selection."""
        protocols = ("PWM", "SBUS")
        protocol_path = ("RC Receiver", "FC Connection", "Protocol")  # Use proper path structure

        # Create mock PairTupleCombobox with invalid current selection
        mock_combobox = MagicMock(spec=PairTupleCombobox)
        mock_combobox.get_selected_key.return_value = "INVALID_PROTOCOL"  # Always returns invalid
        mock_combobox.list_keys = list(protocols)
        editor_with_mocked_root.entry_widgets[protocol_path] = mock_combobox

        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message") as mock_error:
            result = editor_with_mocked_root.update_protocol_combobox_entries(protocols, protocol_path)

            # Should set None (cleared selection) and show error
            expected_tuples = [(p, p) for p in protocols]
            # Only one call with None to clear invalid selection
            mock_combobox.set_entries_tuple.assert_called_once_with(expected_tuples, None)
            mock_combobox.configure.assert_called_once_with(style="comb_input_invalid.TCombobox")
            mock_error.assert_called_once()
            assert "not available" in result

    def test_update_protocol_combobox_entries_no_protocols(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test updating protocol combobox with no available protocols."""
        protocols = ()
        protocol_path = ("RC Receiver", "FC Connection", "Protocol")  # Use proper path structure

        # Create mock PairTupleCombobox
        mock_combobox = MagicMock(spec=PairTupleCombobox)
        mock_combobox.get_selected_key.return_value = "PWM"  # Always returns PWM
        mock_combobox.list_keys = []
        editor_with_mocked_root.entry_widgets[protocol_path] = mock_combobox

        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message") as mock_error:
            result = editor_with_mocked_root.update_protocol_combobox_entries(protocols, protocol_path)

            # Should set empty protocol and show error
            # Only one call with None to clear invalid selection
            mock_combobox.set_entries_tuple.assert_called_once_with([], None)
            mock_error.assert_called_once()
            assert "not available" in result

    def test_update_cell_voltage_limits_entries(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test updating cell voltage limit entries."""
        component_path = ("Battery", "Specifications", "Chemistry")
        chemistry = "LiPo"

        # Set up mock data model
        editor_with_mocked_root.data_model.set_component_value = MagicMock()
        # Need 4 return values: 1 for initial chemistry check + 3 for voltage values
        editor_with_mocked_root.data_model.get_component_value = MagicMock(side_effect=["Different", 4.2, 3.3, 3.0])

        # Set up mock entry widgets - need to add the chemistry path to entry_widgets for the method to proceed
        mock_chemistry_entry = MagicMock()  # Mock for the chemistry combobox
        editor_with_mocked_root.entry_widgets[component_path] = mock_chemistry_entry

        mock_entries = {}
        voltage_paths = [
            ("Battery", "Specifications", "Volt per cell max"),
            ("Battery", "Specifications", "Volt per cell low"),
            ("Battery", "Specifications", "Volt per cell crit"),
        ]
        for path in voltage_paths:
            mock_entry = MagicMock()
            mock_entries[path] = mock_entry
            editor_with_mocked_root.entry_widgets[path] = mock_entry

        # Mock the show_warning_message to prevent blocking dialog
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_warning_message"):
            result = editor_with_mocked_root.update_cell_voltage_limits_entries(component_path, chemistry)

        # Should update data model and all voltage entries
        editor_with_mocked_root.data_model.set_component_value.assert_called_once_with(component_path, chemistry)

        expected_values = [4.2, 3.3, 3.0]
        for i, path in enumerate(voltage_paths):
            mock_entries[path].delete.assert_called_once_with(0, tk.END)
            mock_entries[path].insert.assert_called_once_with(0, str(expected_values[i]))
            mock_entries[path].configure.assert_called_once_with(style="entry_input_valid.TEntry")

        assert result == ""

    def test_update_cell_voltage_limits_entries_no_values(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test updating cell voltage limits with no available values."""
        component_path = ("Battery", "Specifications", "Chemistry")
        chemistry = "Unknown"

        # Set up mock data model to return None values
        editor_with_mocked_root.data_model.set_component_value = MagicMock()
        editor_with_mocked_root.data_model.get_component_value = MagicMock(return_value=None)

        # Set up mock entry widgets - need chemistry path in entry_widgets for method to proceed
        mock_chemistry_entry = MagicMock()
        editor_with_mocked_root.entry_widgets[component_path] = mock_chemistry_entry

        # Set up mock entry widgets for ALL voltage paths to avoid KeyError
        voltage_paths = [
            ("Battery", "Specifications", "Volt per cell max"),
            ("Battery", "Specifications", "Volt per cell low"),
            ("Battery", "Specifications", "Volt per cell crit"),
        ]
        for voltage_path in voltage_paths:
            mock_entry = MagicMock()
            editor_with_mocked_root.entry_widgets[voltage_path] = mock_entry

        # Mock the show_warning_message to prevent blocking dialog
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_warning_message"):
            result = editor_with_mocked_root.update_cell_voltage_limits_entries(component_path, chemistry)

        # Should return error message
        assert "No valid value found for" in result
        # None of the entries should be modified since all values are None
        for voltage_path in voltage_paths:
            editor_with_mocked_root.entry_widgets[voltage_path].delete.assert_not_called()

    def test_add_entry_or_combobox_with_combobox_values(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test adding combobox when values are available."""
        value = "PWM"
        mock_entry_frame = MagicMock()
        path = ("RC Receiver", "FC Connection", "Protocol")  # Use proper 3-level path

        editor_with_mocked_root.data_model.get_combobox_values_for_path = MagicMock(return_value=("PWM", "SBUS", "PPM"))

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_component_editor.PairTupleCombobox"
            ) as mock_combobox_class,
        ):
            mock_combobox = MagicMock()
            mock_combobox_class.return_value = mock_combobox

            result = editor_with_mocked_root.add_entry_or_combobox(value, mock_entry_frame, path)

            # Should create combobox with proper values and bindings
            mock_combobox_class.assert_called_once()
            mock_combobox.bind.assert_called()  # Should bind various events
            assert result == mock_combobox

    def test_add_entry_or_combobox_optional_field(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test adding entry for optional field."""
        value = "test_value"
        mock_entry_frame = MagicMock()
        path = ("Motor", "Specifications", "Notes")  # Use proper 3-level path

        editor_with_mocked_root.data_model.get_combobox_values_for_path = MagicMock(return_value=())

        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.ttk.Entry") as mock_entry_class:
            mock_entry = MagicMock()
            mock_entry_class.return_value = mock_entry

            result = editor_with_mocked_root.add_entry_or_combobox(value, mock_entry_frame, path, is_optional=True)

            # Should create entry with gray foreground for optional field
            call_args = mock_entry_class.call_args[1]
            assert call_args["foreground"] == "gray"
            mock_entry.insert.assert_called_once_with(0, str(value))
            assert result == mock_entry

    def test_add_entry_or_combobox_fc_connection_type(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test adding combobox for FC connection type with special binding."""
        value = "UART"
        mock_entry_frame = MagicMock()
        path = ("RC Receiver", "FC Connection", "Type")  # Use proper component name to match FC_CONNECTION_TYPE_PATHS

        editor_with_mocked_root.data_model.get_combobox_values_for_path = MagicMock(return_value=("UART", "SPI", "I2C"))

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_component_editor.PairTupleCombobox"
            ) as mock_combobox_class,
            patch("ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox.update_combobox_width"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.update_combobox_width"),
        ):
            mock_combobox = MagicMock()
            mock_combobox_class.return_value = mock_combobox

            result = editor_with_mocked_root.add_entry_or_combobox(value, mock_entry_frame, path)

            # Should create combobox with proper values and bindings
            mock_combobox_class.assert_called_once()
            mock_combobox.bind.assert_called()  # Should bind various events
            assert result == mock_combobox

    def test_add_entry_or_combobox_battery_chemistry(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test adding combobox for battery chemistry with special binding."""
        value = "LiPo"
        mock_entry_frame = MagicMock()
        path = ("Battery", "Specifications", "Chemistry")

        editor_with_mocked_root.data_model.get_combobox_values_for_path = MagicMock(return_value=("LiPo", "LiIon", "NiMH"))

        with (
            patch(
                "ardupilot_methodic_configurator.frontend_tkinter_component_editor.PairTupleCombobox"
            ) as mock_combobox_class,
            patch("ardupilot_methodic_configurator.frontend_tkinter_autoresize_combobox.update_combobox_width"),
            patch("ardupilot_methodic_configurator.frontend_tkinter_pair_tuple_combobox.update_combobox_width"),
        ):
            mock_combobox = MagicMock()
            mock_combobox_class.return_value = mock_combobox

            editor_with_mocked_root.add_entry_or_combobox(value, mock_entry_frame, path)

            # Should bind ComboboxSelected event for voltage update
            # The actual calls include the event name as first argument and function as second
            bind_calls = mock_combobox.bind.call_args_list
            bound_events = [call[0][0] for call in bind_calls]  # Extract just the event names
            assert "<<ComboboxSelected>>" in bound_events

    def test_validate_entry_limits_ui_private_method(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test the private validation method for entry limits."""
        mock_event = MagicMock()
        mock_event.type = tk.EventType.FocusOut
        mock_entry = MagicMock()
        mock_entry.get.return_value = "1000"
        path = ("Motor", "Specifications", "KV")  # Use proper 3-level path

        editor_with_mocked_root.data_model.validate_entry_limits = MagicMock(return_value=("", None))
        editor_with_mocked_root.data_model.set_component_value = MagicMock()

        result = editor_with_mocked_root._validate_entry_limits_ui(mock_event, mock_entry, path)

        # Should validate and update data model
        editor_with_mocked_root.data_model.validate_entry_limits.assert_called_once_with("1000", path)
        editor_with_mocked_root.data_model.set_component_value.assert_called_once_with(path, "1000")
        mock_entry.configure.assert_called_once_with(style="entry_input_valid.TEntry")
        assert result is True

    def test_validate_combobox_valid_value(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test combobox validation with valid value."""
        mock_event = MagicMock()
        mock_event.type = "10"  # FocusOut event

        # Create a mock that behaves like a PairTupleCombobox
        mock_combobox = MagicMock(spec=PairTupleCombobox)
        mock_combobox.get_selected_key.return_value = "PWM"
        mock_combobox.list_keys = ["PWM", "SBUS", "PPM"]
        mock_event.widget = mock_combobox

        path = ("RC Receiver", "FC Connection", "Protocol")  # Use proper path structure

        result = editor_with_mocked_root._validate_combobox(mock_event, path)

        mock_combobox.configure.assert_called_once_with(style="comb_input_valid.TCombobox")
        assert result is True

    def test_validate_combobox_invalid_value(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test combobox validation with invalid value."""
        mock_event = MagicMock()
        mock_event.type = "10"  # FocusOut event

        # Create a mock that behaves like a PairTupleCombobox
        mock_combobox = MagicMock(spec=PairTupleCombobox)
        mock_combobox.get_selected_key.return_value = "INVALID"
        mock_combobox.list_keys = ["PWM", "SBUS", "PPM"]
        mock_combobox.dropdown_is_open = True  # Simulate dropdown was open
        mock_event.widget = mock_combobox

        path = ("RC", "Protocol")

        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message") as mock_error:
            result = editor_with_mocked_root._validate_combobox(mock_event, path)

            mock_combobox.configure.assert_called_once_with(style="comb_input_invalid.TCombobox")
            mock_error.assert_called_once()
            assert result is False

    def test_validate_combobox_invalid_value_no_focusout(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test combobox validation with invalid value but not FocusOut event."""
        mock_event = MagicMock()
        mock_event.type = "3"  # Not FocusOut event (10) or Return KeyPress (2)

        # Create a mock that behaves like a PairTupleCombobox
        mock_combobox = MagicMock(spec=PairTupleCombobox)
        mock_combobox.get_selected_key.return_value = "INVALID"
        mock_combobox.list_keys = ["PWM", "SBUS", "PPM"]
        mock_event.widget = mock_combobox

        path = ("RC", "Protocol")

        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message") as mock_error:
            result = editor_with_mocked_root._validate_combobox(mock_event, path)

            mock_combobox.configure.assert_called_once_with(style="comb_input_invalid.TCombobox")
            mock_error.assert_not_called()  # Should not show error for non-FocusOut/non-Return events
            assert result is False

    def test_validate_entry_limits_ui_valid(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test entry limits validation with valid value."""
        mock_event = MagicMock()
        mock_event.type = "10"  # FocusOut event
        mock_entry = MagicMock()
        mock_entry.get.return_value = "1000"
        path = ("Motor", "Specifications", "KV")  # Use proper 3-level path

        editor_with_mocked_root.data_model.validate_entry_limits = MagicMock(return_value=("", None))
        editor_with_mocked_root.data_model.set_component_value = MagicMock()

        result = editor_with_mocked_root._validate_entry_limits_ui(mock_event, mock_entry, path)

        editor_with_mocked_root.data_model.validate_entry_limits.assert_called_once_with("1000", path)
        editor_with_mocked_root.data_model.set_component_value.assert_called_once_with(path, "1000")
        mock_entry.configure.assert_called_once_with(style="entry_input_valid.TEntry")
        assert result is True

    def test_validate_entry_limits_ui_invalid_with_correction(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test entry limits validation with invalid value that gets corrected."""
        mock_event = MagicMock()
        mock_event.type = "10"  # FocusOut event
        mock_entry = MagicMock()
        mock_entry.get.return_value = "99999"
        path = ("Motor", "Specifications", "KV")  # Use proper 3-level path

        editor_with_mocked_root.data_model.validate_entry_limits = MagicMock(return_value=("Value too high", "8000"))

        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message") as mock_error:
            result = editor_with_mocked_root._validate_entry_limits_ui(mock_event, mock_entry, path)

            # Should correct the value and show error
            mock_entry.delete.assert_called_once_with(0, tk.END)
            mock_entry.insert.assert_called_once_with(0, "8000")
            mock_entry.configure.assert_called_once_with(style="entry_input_invalid.TEntry")
            mock_error.assert_called_once()
            assert result is False

    def test_validate_entry_limits_ui_voltage_path(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test entry limits validation for voltage paths."""
        mock_event = MagicMock()
        mock_event.type = "10"  # FocusOut event
        mock_entry = MagicMock()
        mock_entry.get.return_value = "4.2"
        path = ("Battery", "Specifications", "Volt per cell max")

        # Ensure validate_cell_voltage is a mock and set up both validation methods
        editor_with_mocked_root.data_model.validate_cell_voltage = MagicMock(return_value=("", None))
        editor_with_mocked_root.data_model.validate_entry_limits = MagicMock(return_value=("", None))
        editor_with_mocked_root.data_model.set_component_value = MagicMock()

        result = editor_with_mocked_root._validate_entry_limits_ui(mock_event, mock_entry, path)

        editor_with_mocked_root.data_model.validate_entry_limits.assert_called_once_with("4.2", path)
        assert result is True


class TestArgumentParser(SharedTestArgumentParser):
    """Test cases for the argument_parser function."""

    # All test methods are inherited from SharedTestArgumentParser to avoid duplication


class TestIntegrationScenarios:
    """Integration test scenarios for ComponentEditorWindow."""

    def test_complete_validation_workflow(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test complete validation workflow from entry to data model."""
        # Set up a complete scenario with various entry types
        mock_combobox = MagicMock(spec=ttk.Combobox)
        mock_combobox.get.return_value = "PWM"
        mock_entry = MagicMock()
        mock_entry.get.return_value = "1000"

        editor_with_mocked_root.entry_widgets = {
            ("RC", "Protocol"): mock_combobox,
            ("Motor", "KV"): mock_entry,
        }

        # Mock successful validation
        editor_with_mocked_root.data_model.validate_all_data = MagicMock(return_value=(True, []))
        editor_with_mocked_root.data_model.get_combobox_values_for_path = MagicMock(return_value=("PWM", "SBUS"))
        editor_with_mocked_root.data_model.validate_entry_limits = MagicMock(return_value=("", None))

        result = editor_with_mocked_root.validate_data_and_highlight_errors_in_red()

        # Should validate successfully
        assert result == ""
        editor_with_mocked_root.data_model.validate_all_data.assert_called_once()

    def test_fc_parameter_processing_workflow(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test flight controller parameter processing workflow."""
        # Simulate processing FC parameters
        fc_params = {
            "SERIAL1_PROTOCOL": 23,
            "RC_PROTOCOLS": 1,
            "BATT_MONITOR": 4,
        }
        doc = {
            "SERIAL1_PROTOCOL": "Serial port 1 protocol",
            "RC_PROTOCOLS": "RC protocols",
            "BATT_MONITOR": "Battery monitor type",
        }

        editor_with_mocked_root.data_model.process_fc_parameters = MagicMock()
        editor_with_mocked_root.set_values_from_fc_parameters(fc_params, doc)

        # Should delegate to data model
        editor_with_mocked_root.data_model.process_fc_parameters.assert_called_once_with(fc_params, doc)

    def test_vehicle_setup_workflow(self, editor_with_mocked_root: ComponentEditorWindow) -> None:
        """Test complete vehicle setup workflow."""
        # Simulate setting up a new vehicle
        with patch.object(editor_with_mocked_root, "set_component_value_and_update_ui") as mock_set_value:
            # Set vehicle type and version
            editor_with_mocked_root.set_vehicle_type_and_version("ArduCopter", "4.6.x")

            # Set FC details
            editor_with_mocked_root.data_model.is_fc_manufacturer_valid = MagicMock(return_value=True)
            editor_with_mocked_root.data_model.is_fc_model_valid = MagicMock(return_value=True)
            editor_with_mocked_root.set_fc_manufacturer("Matek")
            editor_with_mocked_root.set_fc_model("H743 SLIM")
            editor_with_mocked_root.set_mcu_series("STM32H7xx")

            # Should update all relevant fields
            expected_calls = [
                (("Flight Controller", "Firmware", "Type"), "ArduCopter"),
                (("Flight Controller", "Firmware", "Version"), "4.6.x"),
                (("Flight Controller", "Product", "Manufacturer"), "Matek"),
                (("Flight Controller", "Product", "Model"), "H743 SLIM"),
                (("Flight Controller", "Specifications", "MCU Series"), "STM32H7xx"),
            ]

            for expected_path, expected_value in expected_calls:
                mock_set_value.assert_any_call(expected_path, expected_value)

            assert mock_set_value.call_count == len(expected_calls)


class TestConnectionTypeProtocolChanges:
    """Unit tests for connection type and protocol combobox interactions."""

    def test_connection_type_change_updates_protocol_combobox_options_and_clears_invalid_selection(
        self, editor_with_mocked_root
    ) -> None:
        """
        Connection type change updates protocol combobox options and clears invalid selections.

        GIVEN: RC receiver has a protocol selected that becomes invalid when connection type changes
        WHEN: User changes the connection type to one that doesn't support the current protocol
        THEN: Protocol combobox options are updated to only show valid protocols
        AND: Invalid protocol selection is cleared with appropriate error message
        AND: User is notified of the incompatible protocol selection
        """
        editor = editor_with_mocked_root

        # GIVEN: Create a mock PairTupleCombobox for the protocol field
        mock_protocol_combobox = MagicMock(spec=PairTupleCombobox)
        mock_protocol_combobox.get_selected_key.return_value = "CRSF"  # Initially selected protocol
        mock_protocol_combobox.list_keys = ["CRSF", "SBUS", "PPM"]  # Initially available protocols
        mock_protocol_combobox.set_entries_tuple = MagicMock()
        mock_protocol_combobox.configure = MagicMock()
        mock_protocol_combobox.update_idletasks = MagicMock()

        # Make set_entries_tuple update the list_keys to simulate real behavior
        def update_list_keys(protocol_tuples, selected_element) -> None:
            mock_protocol_combobox.list_keys = [t[0] for t in protocol_tuples]  # Extract keys from tuples
            # Update get_selected_key to return the selected element
            mock_protocol_combobox.get_selected_key.return_value = selected_element

        mock_protocol_combobox.set_entries_tuple.side_effect = update_list_keys

        # Add the mock combobox to the editor's entry widgets
        protocol_path = ("RC Receiver", "FC Connection", "Protocol")
        editor.entry_widgets[protocol_path] = mock_protocol_combobox

        # Mock the error message display to capture it
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message") as mock_show_error:
            # WHEN: Connection type changes to one that only supports PWM and PPM (not CRSF)
            result = editor.update_protocol_combobox_entries(("PWM", "PPM"), protocol_path)

            # THEN: Protocol combobox is updated with new options
            mock_protocol_combobox.set_entries_tuple.assert_called()
            # Only one call with None to clear invalid selection
            assert mock_protocol_combobox.set_entries_tuple.call_count == 1

            # AND: Error message is shown for invalid protocol
            mock_show_error.assert_called_once()
            error_args = mock_show_error.call_args[0]
            assert "CRSF" in error_args[1]  # Protocol name in error message
            assert "not available" in error_args[1]  # Error message content

            # AND: Combobox is styled as invalid
            mock_protocol_combobox.configure.assert_called_with(style="comb_input_invalid.TCombobox")

            # AND: Method returns the error message
            assert "CRSF" in result
            assert "not available" in result

    def test_connection_type_change_preserves_valid_protocol_selection(self, editor_with_mocked_root) -> None:
        """
        Connection type change preserves valid protocol selections.

        GIVEN: RC receiver has a protocol selected that remains valid when connection type changes
        WHEN: User changes the connection type to one that still supports the current protocol
        THEN: Protocol combobox options are updated
        AND: Valid protocol selection is preserved
        AND: No error messages are shown
        """
        editor = editor_with_mocked_root

        # GIVEN: Create a mock PairTupleCombobox for the protocol field
        mock_protocol_combobox = MagicMock(spec=PairTupleCombobox)
        mock_protocol_combobox.get_selected_key.return_value = "PWM"  # Initially selected protocol
        mock_protocol_combobox.list_keys = ["PWM", "PPM"]  # New valid protocols include PWM
        mock_protocol_combobox.set_entries_tuple = MagicMock()
        mock_protocol_combobox.configure = MagicMock()
        mock_protocol_combobox.update_idletasks = MagicMock()

        # Add the mock combobox to the editor's entry widgets
        protocol_path = ("RC Receiver", "FC Connection", "Protocol")
        editor.entry_widgets[protocol_path] = mock_protocol_combobox

        # Mock the error message display to ensure it's not called
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message") as mock_show_error:
            # WHEN: Connection type changes to one that supports PWM
            result = editor.update_protocol_combobox_entries(("PWM", "PPM"), protocol_path)

            # THEN: Protocol combobox is updated with new options
            mock_protocol_combobox.set_entries_tuple.assert_called_once()
            # Should preserve the current selection since PWM is still valid

            # AND: No error messages are shown
            mock_show_error.assert_not_called()

            # AND: No styling changes for invalid input
            mock_protocol_combobox.configure.assert_not_called()

            # AND: Method returns empty string (no errors)
            assert result == ""

    def test_connection_type_change_updates_protocol_combobox_options_and_clears_invalid_selection_via_add_entry_or_combobox_workflow(  # noqa: E501 # pylint: disable=line-too-long, too-many-locals
        self, editor_with_mocked_root
    ) -> None:
        """
        Test connection type change updates protocol combobox options via add_entry_or_combobox workflow.

        GIVEN: User has both Type and Protocol combobox widgets created via add_entry_or_combobox
        WHEN: Connection type changes to one that doesn't support the current protocol
        THEN: Protocol combobox options are updated to only show valid protocols for the new type
        AND: Invalid protocol selection is cleared with appropriate error message
        AND: User is notified of the incompatible protocol selection
        """
        editor = editor_with_mocked_root

        # GIVEN: Create both Type and Protocol combobox widgets using add_entry_or_combobox
        type_path = ("RC Receiver", "FC Connection", "Type")
        protocol_path = ("RC Receiver", "FC Connection", "Protocol")

        # Mock the data model to return combobox values for these paths
        def mock_get_combobox_values(path) -> tuple:
            if path == type_path:
                return ("SERIAL1", "SERIAL2", "RCin/SBUS")
            if path == protocol_path:
                return ("SBUS", "PPM", "DSM")
            return ()

        editor.data_model.get_combobox_values_for_path.side_effect = mock_get_combobox_values

        # Create mock frames for the widgets
        type_frame = MagicMock()
        protocol_frame = MagicMock()

        # Mock PairTupleCombobox to avoid Tkinter issues
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.PairTupleCombobox") as mock_ptc_class:
            # Configure the mock to return mock objects with required attributes
            mock_type_widget = MagicMock()
            mock_type_widget.list_keys = ["SERIAL1", "SERIAL2", "RCin/SBUS"]
            mock_type_widget.get_selected_key.return_value = "SERIAL1"
            mock_type_widget.configure = MagicMock()

            mock_protocol_widget = MagicMock(spec=PairTupleCombobox)
            mock_protocol_widget.list_keys = ["SBUS", "PPM", "DSM"]
            mock_protocol_widget.get_selected_key.return_value = "SBUS"
            mock_protocol_widget.configure = MagicMock()

            # Mock set_entries_tuple to update list_keys
            def mock_set_entries_tuple(entries, selection) -> None:
                mock_protocol_widget.list_keys = [key for key, _ in entries]
                mock_protocol_widget.get_selected_key.return_value = selection

            mock_protocol_widget.set_entries_tuple = mock_set_entries_tuple

            # Make the constructor return different mocks for each call
            mock_ptc_class.side_effect = [mock_type_widget, mock_protocol_widget]

            # Create the Type combobox widget (this would normally be done by add_entry_or_combobox)
            type_widget = editor.add_entry_or_combobox("SERIAL1", type_frame, type_path, is_optional=False)
            protocol_widget = editor.add_entry_or_combobox("SBUS", protocol_frame, protocol_path, is_optional=False)

        # The widgets should be PairTupleCombobox instances (mocked)
        assert type_widget is not None
        assert protocol_widget is not None

        # Add widgets to entry_widgets (normally done by _create_leaf_widget_ui)
        editor.entry_widgets[type_path] = type_widget
        editor.entry_widgets[protocol_path] = protocol_widget

        # Mock the error message display to capture it
        with patch("ardupilot_methodic_configurator.frontend_tkinter_component_editor.show_error_message") as mock_show_error:
            # WHEN: Connection type changes to RCin/SBUS (which may not support SBUS protocol)
            result = editor.update_component_protocol_combobox_entries(type_path, "RCin/SBUS")

            # THEN: Protocol combobox options are updated to protocols valid for RCin/SBUS
            # Get the expected protocols for RCin/SBUS from the data model
            expected_rcin_protocols = editor.data_model.get_combobox_values_for_path(protocol_path)
            assert protocol_widget.list_keys == list(expected_rcin_protocols)

            # AND: Check if SBUS is still valid for RCin/SBUS
            if "SBUS" not in expected_rcin_protocols:
                # The widget should have been updated with None selection
                # This is tested indirectly through the error message

                # AND: Error message is shown for invalid protocol
                mock_show_error.assert_called_once()
                error_args = mock_show_error.call_args[0]
                assert "SBUS" in error_args[1]  # Protocol name in error message
                assert "not available" in error_args[1]  # Error message content

                # AND: Combobox is styled as invalid
                protocol_widget.configure.assert_called_with(style="comb_input_invalid.TCombobox")

                # AND: Method returns the error message
                assert "SBUS" in result
                assert "not available" in result
            else:
                # If SBUS is valid for RCin/SBUS, no error should occur
                mock_show_error.assert_not_called()
                assert result == ""
