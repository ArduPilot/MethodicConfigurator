#!/usr/bin/env python3

"""
Unit tests for vehicle components validation internal implementation.

These tests verify the internal implementation details of the ComponentDataModelValidation class.
They test private methods and attributes that are not part of the public API.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest
from test_data_model_vehicle_components_common import ComponentDataModelFixtures

from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents
from ardupilot_methodic_configurator.data_model_vehicle_components_json_schema import VehicleComponentsJsonSchema
from ardupilot_methodic_configurator.data_model_vehicle_components_validation import (
    SERIAL_BUS_LABELS,
    SERIAL_DISPLAY_TO_KEY,
    ComponentDataModelValidation,
)

# pylint: disable=protected-access


class TestValidationInternals:
    """Unit tests for ComponentDataModelValidation internal implementation."""

    @pytest.fixture
    def empty_model(self) -> ComponentDataModelValidation:
        """Create empty validation model for testing."""
        vehicle_components = VehicleComponents()
        schema = VehicleComponentsJsonSchema(vehicle_components.load_schema())
        component_datatypes = schema.get_all_value_datatypes()
        return ComponentDataModelValidation({}, component_datatypes, schema)

    @pytest.fixture
    def realistic_model(self) -> ComponentDataModelValidation:
        """Create realistic validation model for testing."""
        return ComponentDataModelFixtures.create_realistic_model(ComponentDataModelValidation)

    def test_update_possible_choices_for_rc_receiver_none_connection(self, realistic_model) -> None:
        """Test _update_possible_choices_for_path with RC Receiver None connection."""
        model = realistic_model
        model.init_possible_choices({})

        model._update_possible_choices_for_path(("RC Receiver", "FC Connection", "Type"), "None")
        protocol_choices = model._possible_choices.get(("RC Receiver", "FC Connection", "Protocol"), ())

        assert protocol_choices == ("None",)

    def test_update_possible_choices_for_rc_receiver_serial_connection(self, realistic_model) -> None:
        """Test _update_possible_choices_for_path with RC Receiver serial connection."""
        model = realistic_model
        model.init_possible_choices({})

        model._update_possible_choices_for_path(("RC Receiver", "FC Connection", "Type"), "SERIAL7")
        protocol_choices = model._possible_choices.get(("RC Receiver", "FC Connection", "Protocol"), ())

        assert len(protocol_choices) > 0
        assert any(protocol in ["CRSF", "SBUS", "PPM"] for protocol in protocol_choices)

    def test_update_possible_choices_for_rc_receiver_rc_port(self, realistic_model) -> None:
        """Test _update_possible_choices_for_path with RC Receiver RCin/SBUS port."""
        model = realistic_model
        model.init_possible_choices({})

        model._update_possible_choices_for_path(("RC Receiver", "FC Connection", "Type"), "RCin/SBUS")
        protocol_choices = model._possible_choices.get(("RC Receiver", "FC Connection", "Protocol"), ())

        assert len(protocol_choices) > 0

    def test_update_possible_choices_for_telemetry_none(self, realistic_model) -> None:
        """Test _update_possible_choices_for_path with Telemetry None connection."""
        model = realistic_model
        model.init_possible_choices({})

        model._update_possible_choices_for_path(("Telemetry", "FC Connection", "Type"), "None")
        protocol_choices = model._possible_choices.get(("Telemetry", "FC Connection", "Protocol"), ())

        assert protocol_choices == ("None",)

    def test_update_possible_choices_for_telemetry_serial(self, realistic_model) -> None:
        """Test _update_possible_choices_for_path with Telemetry serial connection."""
        model = realistic_model
        model.init_possible_choices({})

        model._update_possible_choices_for_path(("Telemetry", "FC Connection", "Type"), "SERIAL1")
        protocol_choices = model._possible_choices.get(("Telemetry", "FC Connection", "Protocol"), ())

        assert len(protocol_choices) > 0
        assert any(protocol in ["MAVLink2", "MAVLink1"] for protocol in protocol_choices)

    def test_update_possible_choices_for_esc_can(self, realistic_model) -> None:
        """Test _update_possible_choices_for_path with ESC CAN connection."""
        model = realistic_model
        model.init_possible_choices({"MOT_PWM_TYPE": {"values": {"0": "Normal", "6": "DShot600"}}})

        model._update_possible_choices_for_path(("ESC", "FC Connection", "Type"), "CAN1")
        protocol_choices = model._possible_choices.get(("ESC", "FC Connection", "Protocol"), ())

        assert protocol_choices == ("DroneCAN",)

    def test_update_possible_choices_for_esc_pwm(self, realistic_model) -> None:
        """Test _update_possible_choices_for_path with ESC PWM connection."""  # pylint: disable=duplicate-code  # Common connection test pattern
        model = realistic_model
        model.init_possible_choices({"MOT_PWM_TYPE": {"values": {"0": "Normal", "6": "DShot600"}}})

        model._update_possible_choices_for_path(("ESC", "FC Connection", "Type"), "Main Out")
        protocol_choices = model._possible_choices.get(("ESC", "FC Connection", "Protocol"), ())

        assert len(protocol_choices) > 0
        # pylint: enable=duplicate-code

    def test_update_possible_choices_for_gnss_none(self, realistic_model) -> None:
        """Test _update_possible_choices_for_path with GNSS Receiver None connection."""
        model = realistic_model
        model.init_possible_choices({})

        model._update_possible_choices_for_path(("GNSS Receiver", "FC Connection", "Type"), "None")
        protocol_choices = model._possible_choices.get(("GNSS Receiver", "FC Connection", "Protocol"), ())

        assert protocol_choices == ("None",)

    def test_update_possible_choices_for_gnss_serial(self, realistic_model) -> None:
        """Test _update_possible_choices_for_path with GNSS Receiver serial connection."""
        model = realistic_model
        model.init_possible_choices({})

        model._update_possible_choices_for_path(("GNSS Receiver", "FC Connection", "Type"), "SERIAL3")
        protocol_choices = model._possible_choices.get(("GNSS Receiver", "FC Connection", "Protocol"), ())

        assert len(protocol_choices) > 0

    def test_update_possible_choices_for_gnss_can(self, realistic_model) -> None:
        """Test _update_possible_choices_for_path with GNSS Receiver CAN connection."""  # pylint: disable=duplicate-code  # Common connection test pattern
        model = realistic_model
        model.init_possible_choices({})

        model._update_possible_choices_for_path(("GNSS Receiver", "FC Connection", "Type"), "CAN1")
        protocol_choices = model._possible_choices.get(("GNSS Receiver", "FC Connection", "Protocol"), ())

        assert len(protocol_choices) > 0
        # pylint: enable=duplicate-code

    def test_update_possible_choices_for_battery_monitor_none(self, realistic_model) -> None:
        """Test _update_possible_choices_for_path with Battery Monitor None connection."""
        model = realistic_model
        model.init_possible_choices({})

        model._update_possible_choices_for_path(("Battery Monitor", "FC Connection", "Type"), "None")
        protocol_choices = model._possible_choices.get(("Battery Monitor", "FC Connection", "Protocol"), ())

        assert protocol_choices == ("None",)

    def test_update_possible_choices_for_battery_monitor_analog(self, realistic_model) -> None:
        """Test _update_possible_choices_for_path with Battery Monitor analog connection."""
        model = realistic_model
        model.init_possible_choices({})

        model._update_possible_choices_for_path(("Battery Monitor", "FC Connection", "Type"), "Analog")
        protocol_choices = model._possible_choices.get(("Battery Monitor", "FC Connection", "Protocol"), ())

        assert len(protocol_choices) > 0

    def test_update_possible_choices_for_battery_monitor_i2c(self, realistic_model) -> None:
        """Test _update_possible_choices_for_path with Battery Monitor I2C connection."""  # pylint: disable=duplicate-code  # Common connection test pattern
        model = realistic_model
        model.init_possible_choices({})

        model._update_possible_choices_for_path(("Battery Monitor", "FC Connection", "Type"), "I2C1")
        protocol_choices = model._possible_choices.get(("Battery Monitor", "FC Connection", "Protocol"), ())

        assert len(protocol_choices) > 0
        # pylint: enable=duplicate-code

    def test_battery_chemistry_attribute_access(self, realistic_model) -> None:
        """Test direct access to _battery_chemistry attribute."""
        assert realistic_model._battery_chemistry == "Lipo"

    def test_battery_chemistry_updated_on_set(self, empty_model) -> None:
        """Test that _battery_chemistry is updated when chemistry is set."""
        model = empty_model

        model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")
        assert model._battery_chemistry == "Lipo"

    def test_possible_choices_structure(self, realistic_model) -> None:
        """Test that _possible_choices has correct structure."""
        model = realistic_model
        model.init_possible_choices({})

        assert isinstance(model._possible_choices, dict)
        assert len(model._possible_choices) > 0

    def test_data_attribute_structure(self, realistic_model) -> None:
        """Test that _data attribute has correct structure."""
        assert isinstance(realistic_model._data, dict)
        assert "Components" in realistic_model._data

    def test_component_datatypes_attribute(self, realistic_model) -> None:
        """Test that _component_datatypes attribute exists and has correct structure."""
        assert hasattr(realistic_model, "_component_datatypes")
        assert isinstance(realistic_model._component_datatypes, dict)


class TestDisplayValueCorrectionInternals:
    """Unit tests for display value correction internal implementation."""

    @pytest.fixture
    def validation_model(self) -> ComponentDataModelValidation:
        """Fixture providing a validation model with realistic test data."""
        return ComponentDataModelFixtures.create_realistic_model(ComponentDataModelValidation)

    def test_correct_display_values_with_serial_labels(self, validation_model) -> None:
        """Test that correct_display_values_in_loaded_data() corrects SERIAL display labels."""
        # Arrange
        initial_data = {
            "Components": {
                "GNSS Receiver": {"FC Connection": {"Type": "GPS1 (SERIAL3)"}},
                "Telemetry": {"FC Connection": {"Type": "Telem1 (SERIAL1)"}},
            },
            "Format version": 1,
        }

        model = ComponentDataModelValidation(initial_data, {}, validation_model.schema)
        model._possible_choices = validation_model._possible_choices
        model._battery_chemistry = validation_model._battery_chemistry

        # Act
        model.correct_display_values_in_loaded_data()

        # Assert
        assert model.get_component_value(("GNSS Receiver", "FC Connection", "Type")) == "SERIAL3"
        assert model.get_component_value(("Telemetry", "FC Connection", "Type")) == "SERIAL1"

    def test_correct_display_values_preserves_key_values(self, validation_model) -> None:
        """Test that correct_display_values_in_loaded_data() preserves already-correct key values."""
        # Arrange
        initial_data = {
            "Components": {
                "RC Receiver": {"FC Connection": {"Type": "SERIAL2"}},
                "ESC": {"FC Connection": {"Type": "CAN1"}},
            },
            "Format version": 1,
        }

        model = ComponentDataModelValidation(initial_data, {}, validation_model.schema)
        model._possible_choices = validation_model._possible_choices
        model._battery_chemistry = validation_model._battery_chemistry

        # Act
        model.correct_display_values_in_loaded_data()

        # Assert
        assert model.get_component_value(("RC Receiver", "FC Connection", "Type")) == "SERIAL2"
        assert model.get_component_value(("ESC", "FC Connection", "Type")) == "CAN1"

    def test_correct_display_values_handles_nested_data(self, validation_model) -> None:
        """Test that correct_display_values_in_loaded_data() handles nested data structures."""
        # Arrange
        initial_data = {
            "Components": {
                "GNSS Receiver": {
                    "FC Connection": {
                        "Type": "GPS2 (SERIAL4)",
                        "Protocol": "uBlox",
                    },
                    "Other Config": {"Setting1": "Value1"},
                }
            },
            "Format version": 1,
        }

        model = ComponentDataModelValidation(initial_data, {}, validation_model.schema)
        model._possible_choices = validation_model._possible_choices
        model._battery_chemistry = validation_model._battery_chemistry

        # Act
        model.correct_display_values_in_loaded_data()

        # Assert
        assert model.get_component_value(("GNSS Receiver", "FC Connection", "Type")) == "SERIAL4"
        assert model.get_component_value(("GNSS Receiver", "FC Connection", "Protocol")) == "uBlox"

    def test_correct_display_values_handles_empty_values(self, validation_model) -> None:
        """Test that correct_display_values_in_loaded_data() handles empty string values."""
        # Arrange
        initial_data = {
            "Components": {"Telemetry": {"FC Connection": {"Type": "", "Protocol": ""}}},
            "Format version": 1,
        }

        model = ComponentDataModelValidation(initial_data, {}, validation_model.schema)
        model._possible_choices = validation_model._possible_choices
        model._battery_chemistry = validation_model._battery_chemistry

        # Act
        model.correct_display_values_in_loaded_data()

        # Assert
        assert model.get_component_value(("Telemetry", "FC Connection", "Type")) == ""

    def test_serial_display_to_key_mapping_consistency(self, validation_model) -> None:
        """Test that SERIAL_DISPLAY_TO_KEY correctly reverses all SERIAL_BUS_LABELS entries."""
        for key, display_label in SERIAL_BUS_LABELS.items():
            # Arrange
            initial_data = {
                "Components": {"RC Receiver": {"FC Connection": {"Type": display_label}}},
                "Format version": 1,
            }

            model = ComponentDataModelValidation(initial_data, {}, validation_model.schema)
            model._possible_choices = validation_model._possible_choices
            model._battery_chemistry = validation_model._battery_chemistry

            # Act
            model.correct_display_values_in_loaded_data()

            # Assert
            result = model.get_component_value(("RC Receiver", "FC Connection", "Type"))
            assert result == key, f"Display '{display_label}' should map to key '{key}'"
            assert SERIAL_DISPLAY_TO_KEY[display_label] == key
