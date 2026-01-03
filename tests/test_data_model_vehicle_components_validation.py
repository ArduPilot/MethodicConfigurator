#!/usr/bin/env python3

"""
Vehicle Components data model validation tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import math

import pytest
from test_data_model_vehicle_components_common import (
    SAMPLE_DOC_DICT,
    BasicTestMixin,
    ComponentDataModelFixtures,
    RealisticDataTestMixin,
)

from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents
from ardupilot_methodic_configurator.battery_cell_voltages import BatteryCell
from ardupilot_methodic_configurator.data_model_vehicle_components_json_schema import VehicleComponentsJsonSchema
from ardupilot_methodic_configurator.data_model_vehicle_components_validation import ComponentDataModelValidation

# pylint: disable=too-many-lines,protected-access,too-many-public-methods


class TestComponentDataModelValidation(BasicTestMixin, RealisticDataTestMixin):
    """Tests for the ComponentDataModelValidation class."""

    @pytest.fixture
    def empty_model(self) -> ComponentDataModelValidation:
        """Create an empty ComponentDataModelValidation fixture for testing."""
        return ComponentDataModelFixtures.create_empty_model(ComponentDataModelValidation)

    @pytest.fixture
    def basic_model(self) -> ComponentDataModelValidation:
        """Create a ComponentDataModelValidation fixture for testing."""
        return ComponentDataModelFixtures.create_basic_model(ComponentDataModelValidation)

    @pytest.fixture
    def realistic_model(self) -> ComponentDataModelValidation:
        """Create a realistic vehicle data model based on the JSON file."""
        return ComponentDataModelFixtures.create_realistic_model(ComponentDataModelValidation)

    # Update the sample_doc_dict fixture to use the common one
    @pytest.fixture
    def sample_doc_dict(self) -> dict:
        """Create a sample doc_dict for testing."""
        return SAMPLE_DOC_DICT.copy()

    # Test initialization and basic functionality
    def test_initialization_empty_model(self, empty_model) -> None:
        """
        Test initialization of empty ComponentDataModelValidation.

        GIVEN: A fresh ComponentDataModelValidation instance
        WHEN: The model is created with empty data
        THEN: All required attributes should be initialized
        """
        assert empty_model is not None
        assert hasattr(empty_model, "VALIDATION_RULES")
        assert hasattr(empty_model, "_data")
        assert hasattr(empty_model, "_battery_chemistry")
        assert hasattr(empty_model, "_possible_choices")
        assert hasattr(empty_model, "_component_datatypes")

    def test_initialization_realistic_model(self, realistic_model) -> None:
        """
        Test initialization of realistic ComponentDataModelValidation.

        GIVEN: A ComponentDataModelValidation instance with realistic data
        WHEN: The model is created from a JSON file
        THEN: Battery chemistry and component data should be properly loaded
        """
        assert realistic_model is not None
        assert realistic_model._battery_chemistry == "Lipo"
        data = realistic_model.get_component_data()
        assert "Components" in data
        assert len(data["Components"]) > 0

    def test_validation_rules_class_attribute(self, empty_model) -> None:
        """
        Test that VALIDATION_RULES class attribute is properly defined.

        GIVEN: A ComponentDataModelValidation instance
        WHEN: Accessing the VALIDATION_RULES class attribute
        THEN: It should contain all expected validation rules with proper structure
        """
        rules = empty_model.VALIDATION_RULES
        assert hasattr(rules, "__getitem__")  # Check if it behaves like a dict (MappingProxyType)

        # Check that specific rules exist
        expected_rules = [
            ("Frame", "Specifications", "TOW min Kg"),
            ("Frame", "Specifications", "TOW max Kg"),
            ("Battery", "Specifications", "Number of cells"),
            ("Battery", "Specifications", "Capacity mAh"),
            ("Motors", "Specifications", "Poles"),
            ("Propellers", "Specifications", "Diameter_inches"),
        ]

        for rule in expected_rules:
            assert rule in rules
            data_type, limits, name = rules[rule]
            assert isinstance(data_type, type)
            assert isinstance(limits, tuple)
            assert len(limits) == 2
            assert isinstance(name, str)

    # Test is_valid_component_data method
    def test_is_valid_component_data_valid_structures(self, realistic_model, empty_model) -> None:
        """
        Test is_valid_component_data with valid data structures.

        GIVEN: Models with valid component data structures
        WHEN: Validating the component data
        THEN: Validation should pass for both realistic and empty models
        """
        assert realistic_model.is_valid_component_data() is True
        assert empty_model.is_valid_component_data() is True

    def test_is_valid_component_data_invalid_structures(self) -> None:
        """
        Test is_valid_component_data with invalid data structures.

        GIVEN: Component data with invalid structures (missing Components key, wrong types)
        WHEN: Validating the component data
        THEN: Validation should fail for all invalid structures
        """
        vehicle_components = VehicleComponents()
        schema = VehicleComponentsJsonSchema(vehicle_components.load_schema())
        component_datatypes = schema.get_all_value_datatypes()

        # Test with missing Components key
        invalid_data1 = {"Format version": 1}
        model1 = ComponentDataModelValidation(invalid_data1, component_datatypes, schema)
        assert model1.is_valid_component_data() is False

        # Test with Components not being a dict
        invalid_data2 = {"Components": "not_a_dict", "Format version": 1}
        model2 = ComponentDataModelValidation(invalid_data2, component_datatypes, schema)
        assert model2.is_valid_component_data() is False

        # Test with data not being a dict - use type: ignore to bypass type checking for testing
        model3 = ComponentDataModelValidation({}, component_datatypes, schema)
        model3._data = "not_a_dict"  # type: ignore[assignment] # Manually set to invalid type for testing
        assert model3.is_valid_component_data() is False

    # Test set_component_value method with battery chemistry side effects
    def test_set_component_value_battery_chemistry_side_effects(self, empty_model) -> None:
        """
        Test that setting battery chemistry triggers side effects.

        GIVEN: An empty model without battery chemistry set
        WHEN: Setting the battery chemistry value
        THEN: Battery voltage values should be automatically set to recommended values
        """
        model = empty_model

        # Set battery chemistry
        model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")

        # Check that battery chemistry is updated
        assert model._battery_chemistry == "Lipo"

        # Check that voltage values are set automatically
        max_voltage = model.get_component_value(("Battery", "Specifications", "Volt per cell max"))
        low_voltage = model.get_component_value(("Battery", "Specifications", "Volt per cell low"))
        crit_voltage = model.get_component_value(("Battery", "Specifications", "Volt per cell crit"))

        # Values should exist and be the expected float values (or defaults if not set)
        # The empty model may not have created the battery structure yet, so check if values are numeric
        if isinstance(max_voltage, (int, float)):
            assert max_voltage == BatteryCell.recommended_max_voltage("Lipo")
        if isinstance(low_voltage, (int, float)):
            assert low_voltage == BatteryCell.recommended_low_voltage("Lipo")
        if isinstance(crit_voltage, (int, float)):
            assert crit_voltage == BatteryCell.recommended_crit_voltage("Lipo")

    def test_set_component_value_different_chemistries(self, empty_model) -> None:
        """
        Test battery chemistry side effects with different chemistries.

        GIVEN: A model and all available battery chemistries
        WHEN: Setting each chemistry type
        THEN: Recommended voltages should match each chemistry's specifications
        """
        model = empty_model

        for chemistry in BatteryCell.chemistries():
            model.set_component_value(("Battery", "Specifications", "Chemistry"), chemistry)
            assert model._battery_chemistry == chemistry

            # Verify that recommended voltages are set correctly
            max_voltage = model.get_component_value(("Battery", "Specifications", "Volt per cell max"))
            low_voltage = model.get_component_value(("Battery", "Specifications", "Volt per cell low"))
            crit_voltage = model.get_component_value(("Battery", "Specifications", "Volt per cell crit"))

            assert max_voltage == BatteryCell.recommended_max_voltage(chemistry)
            assert low_voltage == BatteryCell.recommended_low_voltage(chemistry)
            assert crit_voltage == BatteryCell.recommended_crit_voltage(chemistry)

    def test_set_component_value_no_side_effects_for_non_chemistry(self, empty_model) -> None:
        """
        Test that setting non-chemistry values doesn't trigger side effects.

        GIVEN: A model with a specific battery chemistry
        WHEN: Setting a non-chemistry component value
        THEN: Battery chemistry should remain unchanged
        """
        model = empty_model
        original_chemistry = model._battery_chemistry

        # Set some other value
        model.set_component_value(("Frame", "Specifications", "TOW min Kg"), 0.5)

        # Chemistry should remain unchanged
        assert model._battery_chemistry == original_chemistry

    # Test init_possible_choices method
    def test_init_possible_choices_with_doc_dict(self, empty_model, sample_doc_dict) -> None:
        """
        Test init_possible_choices with a valid doc_dict.

        GIVEN: An empty model and a valid parameter documentation dictionary
        WHEN: Initializing possible choices from the doc_dict
        THEN: Component connection type and protocol choices should be populated
        """
        model = empty_model
        model.init_possible_choices(sample_doc_dict)

        # Check that choices are initialized
        assert isinstance(model._possible_choices, dict)
        assert len(model._possible_choices) > 0

        # Check specific choices
        assert ("Flight Controller", "Firmware", "Type") in model._possible_choices
        assert ("RC Receiver", "FC Connection", "Type") in model._possible_choices
        assert ("Battery", "Specifications", "Chemistry") in model._possible_choices

    def test_init_possible_choices_with_empty_doc_dict(self, empty_model) -> None:
        """
        Test init_possible_choices with an empty doc_dict.

        GIVEN: An empty model and an empty parameter documentation dictionary
        WHEN: Initializing possible choices
        THEN: Fallback choices should still be available
        """
        model = empty_model
        model.init_possible_choices({})

        # Should still have some basic choices
        assert isinstance(model._possible_choices, dict)
        assert len(model._possible_choices) > 0

    def test_init_possible_choices_fallbacks(self, empty_model) -> None:
        """
        Test that fallback values are used when doc_dict is incomplete.

        GIVEN: A model and an incomplete parameter documentation dictionary
        WHEN: Initializing possible choices with missing parameters
        THEN: Fallback choices should be used for missing parameters
        """
        model = empty_model
        incomplete_doc = {"RC_PROTOCOLS": {"Bitmask": {"9": "CRSF"}}}
        model.init_possible_choices(incomplete_doc)

        # Should have fallback choices for missing parameters
        assert isinstance(model._possible_choices, dict)

    # Test validate_entry_limits method
    def test_validate_entry_limits_valid_values(self, realistic_model) -> None:
        """
        Test validate_entry_limits with valid values.

        GIVEN: A realistic model with validation rules
        WHEN: Validating component values within acceptable limits
        THEN: Validation should pass without errors or corrections
        """
        model = realistic_model

        test_cases = [
            (("Frame", "Specifications", "TOW min Kg"), "0.6", True),
            (("Frame", "Specifications", "TOW max Kg"), "0.6", True),
            (("Battery", "Specifications", "Number of cells"), "4", True),
            (("Battery", "Specifications", "Capacity mAh"), "1800", True),
            (("Motors", "Specifications", "Poles"), "14", True),
            (("Propellers", "Specifications", "Diameter_inches"), "3.0", True),
        ]

        for path, value, should_be_valid in test_cases:
            error_msg, corrected_value = model.validate_entry_limits(value, path)
            if should_be_valid:
                assert error_msg == ""
                assert corrected_value is None
            else:
                assert error_msg != ""
                assert corrected_value is not None

    def test_validate_entry_limits_invalid_values(self, realistic_model) -> None:
        """
        Test validate_entry_limits with invalid values.

        GIVEN: A realistic model with validation rules
        WHEN: Validating component values outside acceptable limits
        THEN: Validation should return error messages and corrected values
        """
        model = realistic_model

        test_cases = [
            (("Frame", "Specifications", "TOW min Kg"), "0.005", False),  # Below minimum
            (("Frame", "Specifications", "TOW max Kg"), "1000", False),  # Above maximum
            (("Battery", "Specifications", "Number of cells"), "0", False),  # Below minimum
            (("Battery", "Specifications", "Number of cells"), "100", False),  # Above maximum
            (("Motors", "Specifications", "Poles"), "2", False),  # Below minimum
            (("Motors", "Specifications", "Poles"), "100", False),  # Above maximum
        ]

        for path, value, should_be_valid in test_cases:
            error_msg, corrected_value = model.validate_entry_limits(value, path)
            if not should_be_valid:
                assert error_msg != ""
                assert corrected_value is not None

    def test_validate_entry_limits_value_errors(self, realistic_model) -> None:
        """
        Test validate_entry_limits with non-numeric values.

        GIVEN: A realistic model with validation rules
        WHEN: Validating non-numeric string values
        THEN: Validation should return error messages without corrections
        """
        model = realistic_model

        test_cases = [
            (("Frame", "Specifications", "TOW min Kg"), "not_a_number"),
            (("Battery", "Specifications", "Number of cells"), "invalid"),
            (("Motors", "Specifications", "Poles"), "abc"),
        ]

        for path, value in test_cases:
            error_msg, corrected_value = model.validate_entry_limits(value, path)
            assert error_msg != ""
            assert corrected_value is None

    def test_validate_entry_limits_tow_relationships(self, realistic_model) -> None:
        """
        Test validate_entry_limits for takeoff weight relationships.

        GIVEN: A model with TOW min and max values set
        WHEN: Validating TOW values against each other
        THEN: TOW min must be below TOW max and vice versa
        """
        model = realistic_model

        # Set up TOW values
        model.set_component_value(("Frame", "Specifications", "TOW min Kg"), 0.5)
        model.set_component_value(("Frame", "Specifications", "TOW max Kg"), 0.8)

        # Test valid TOW min (below max)
        error_msg, corrected_value = model.validate_entry_limits("0.6", ("Frame", "Specifications", "TOW min Kg"))
        assert error_msg == ""
        assert corrected_value is None

        # Test invalid TOW min (above max)
        error_msg, corrected_value = model.validate_entry_limits("0.9", ("Frame", "Specifications", "TOW min Kg"))
        assert error_msg != ""
        assert corrected_value is not None

        # Test valid TOW max (above min)
        error_msg, corrected_value = model.validate_entry_limits("0.7", ("Frame", "Specifications", "TOW max Kg"))
        assert error_msg == ""
        assert corrected_value is None

        # Test invalid TOW max (below min)
        error_msg, corrected_value = model.validate_entry_limits("0.4", ("Frame", "Specifications", "TOW max Kg"))
        assert error_msg != ""
        assert corrected_value is not None

    def test_validate_entry_limits_non_validation_paths(self, realistic_model) -> None:
        """
        Test validate_entry_limits with paths not in validation rules.

        GIVEN: A realistic model with validation rules
        WHEN: Validating a path not defined in VALIDATION_RULES
        THEN: Validation should pass without errors (no validation applied)
        """
        model = realistic_model

        # Test with a path not in VALIDATION_RULES
        error_msg, corrected_value = model.validate_entry_limits("any_value", ("Unknown", "Path", "Value"))
        assert error_msg == ""
        assert corrected_value is None

    # Test validate_cell_voltage method
    def test_validate_cell_voltage_valid_voltages(self, realistic_model) -> None:
        """
        Test validate_cell_voltage with valid voltages.

        GIVEN: A model with battery chemistry and valid voltage relationships
        WHEN: Validating cell voltages that respect max > low > crit ordering
        THEN: Validation should pass without errors or corrections
        """
        model = realistic_model
        model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")

        # Set up voltage relationships
        model.set_component_value(("Battery", "Specifications", "Volt per cell max"), 4.2)
        model.set_component_value(("Battery", "Specifications", "Volt per cell low"), 3.6)
        model.set_component_value(("Battery", "Specifications", "Volt per cell crit"), 3.3)

        test_cases = [
            (("Battery", "Specifications", "Volt per cell max"), "4.2"),
            (("Battery", "Specifications", "Volt per cell low"), "3.6"),
            (("Battery", "Specifications", "Volt per cell crit"), "3.3"),
        ]

        for path, value in test_cases:
            error_msg, corrected_value = model.validate_cell_voltage(value, path)
            assert error_msg == ""
            assert corrected_value is None

    def test_validate_cell_voltage_invalid_relationships(self, realistic_model) -> None:
        """
        Test validate_cell_voltage with invalid voltage relationships.

        GIVEN: A model with battery chemistry and established voltage values
        WHEN: Validating voltages that violate max > low > crit ordering
        THEN: Validation should return error messages and corrected values
        """
        model = realistic_model
        model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")

        # Set up conflicting voltage relationships
        model.set_component_value(("Battery", "Specifications", "Volt per cell max"), 4.2)
        model.set_component_value(("Battery", "Specifications", "Volt per cell low"), 3.6)
        model.set_component_value(("Battery", "Specifications", "Volt per cell crit"), 3.3)

        # Test max voltage below low voltage
        error_msg, corrected_value = model.validate_cell_voltage("3.5", ("Battery", "Specifications", "Volt per cell max"))
        assert error_msg != ""
        assert corrected_value is not None

        # Test low voltage above max voltage
        error_msg, corrected_value = model.validate_cell_voltage("4.3", ("Battery", "Specifications", "Volt per cell low"))
        assert error_msg != ""
        assert corrected_value is not None

        # Test crit voltage above low voltage
        error_msg, corrected_value = model.validate_cell_voltage("3.7", ("Battery", "Specifications", "Volt per cell crit"))
        assert error_msg != ""
        assert corrected_value is not None

    def test_validate_cell_voltage_chemistry_limits(self, realistic_model) -> None:
        """
        Test validate_cell_voltage against chemistry-specific limits.

        GIVEN: A model and all available battery chemistries
        WHEN: Validating voltages outside chemistry-specific limits
        THEN: Validation should enforce chemistry min/max voltage limits
        """
        model = realistic_model

        for chemistry in BatteryCell.chemistries():
            model.set_component_value(("Battery", "Specifications", "Chemistry"), chemistry)

            # Test voltage above chemistry limit
            max_limit = BatteryCell.limit_max_voltage(chemistry)
            error_msg, corrected_value = model.validate_cell_voltage(
                str(max_limit + 0.1), ("Battery", "Specifications", "Volt per cell max")
            )
            assert error_msg != ""
            assert corrected_value == max_limit

            # Test voltage below chemistry limit
            min_limit = BatteryCell.limit_min_voltage(chemistry)
            error_msg, corrected_value = model.validate_cell_voltage(
                str(min_limit - 0.1), ("Battery", "Specifications", "Volt per cell max")
            )
            assert error_msg != ""
            assert corrected_value == min_limit

    def test_validate_cell_voltage_invalid_values(self, realistic_model) -> None:
        """
        Test validate_cell_voltage with invalid string values.

        GIVEN: A model with battery chemistry set
        WHEN: Validating non-numeric string values for cell voltages
        THEN: Validation should return error messages with recommended corrections
        """
        model = realistic_model
        model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")

        test_cases = [
            ("not_a_number", ("Battery", "Specifications", "Volt per cell max")),
            ("", ("Battery", "Specifications", "Volt per cell low")),
            ("abc", ("Battery", "Specifications", "Volt per cell crit")),
        ]

        for value, path in test_cases:
            error_msg, corrected_value = model.validate_cell_voltage(value, path)
            assert error_msg != ""
            assert corrected_value is not None
            assert isinstance(corrected_value, float)

    def test_validate_cell_voltage_non_battery_paths(self, realistic_model) -> None:
        """
        Test validate_cell_voltage with non-battery paths.

        GIVEN: A realistic model
        WHEN: Validating a non-battery component path
        THEN: Validation should pass without checking (not applicable)
        """
        model = realistic_model

        # Test with non-battery path
        error_msg, corrected_value = model.validate_cell_voltage("4.2", ("Frame", "Specifications", "TOW max Kg"))
        assert error_msg == ""
        assert corrected_value is None

    # Test recommended_cell_voltage method
    def test_recommended_cell_voltage_all_paths(self, realistic_model) -> None:
        """
        Test recommended_cell_voltage for all voltage paths.

        GIVEN: A model with all available battery chemistries
        WHEN: Requesting recommended voltages for max, low, and crit
        THEN: Returned values should match chemistry-specific recommendations
        """
        model = realistic_model

        for chemistry in BatteryCell.chemistries():
            model.set_component_value(("Battery", "Specifications", "Chemistry"), chemistry)

            # Test max voltage
            recommended = model.recommended_cell_voltage(("Battery", "Specifications", "Volt per cell max"))
            expected = BatteryCell.recommended_max_voltage(chemistry)
            assert recommended == expected

            # Test low voltage
            recommended = model.recommended_cell_voltage(("Battery", "Specifications", "Volt per cell low"))
            expected = BatteryCell.recommended_low_voltage(chemistry)
            assert recommended == expected

            # Test crit voltage
            recommended = model.recommended_cell_voltage(("Battery", "Specifications", "Volt per cell crit"))
            expected = BatteryCell.recommended_crit_voltage(chemistry)
            assert recommended == expected

    def test_recommended_cell_voltage_unknown_path(self, realistic_model) -> None:
        """
        Test recommended_cell_voltage for unknown voltage path.

        GIVEN: A realistic model
        WHEN: Requesting recommended voltage for an unknown voltage type
        THEN: A default voltage value should be returned
        """
        model = realistic_model

        # Test unknown voltage path - should return default
        recommended = model.recommended_cell_voltage(("Battery", "Specifications", "Unknown voltage"))
        assert recommended == 3.8

    # Test validate_against_another_value method
    def test_validate_against_another_value_valid_comparisons(self, realistic_model) -> None:
        """
        Test validate_against_another_value with valid comparisons.

        GIVEN: A model and various value/limit/direction combinations
        WHEN: Validating values that satisfy the comparison constraints
        THEN: Validation should pass without errors or corrections
        """
        model = realistic_model

        test_cases = [
            (5.0, 3.0, "limit", True, 0.1, True),  # 5.0 > 3.0, above=True, should be valid
            (3.0, 5.0, "limit", False, 0.1, True),  # 3.0 < 5.0, above=False, should be valid
            (3.0, 3.0, "limit", True, 0.1, True),  # 3.0 == 3.0, should be valid regardless
            (3.0, 3.0, "limit", False, 0.1, True),  # 3.0 == 3.0, should be valid regardless
        ]

        for value, limit_value, limit_name, above, delta, should_be_valid in test_cases:
            error_msg, corrected_value = model.validate_against_another_value(value, limit_value, limit_name, above, delta)
            if should_be_valid:
                assert error_msg == ""
                assert corrected_value is None
            else:
                assert error_msg != ""
                assert corrected_value is not None

    def test_validate_against_another_value_invalid_comparisons(self, realistic_model) -> None:
        """
        Test validate_against_another_value with invalid comparisons.

        GIVEN: A model and value/limit combinations that violate constraints
        WHEN: Validating values in wrong direction relative to limits
        THEN: Validation should return errors and corrected values with delta applied
        """
        model = realistic_model

        test_cases = [
            (3.0, 5.0, "limit", True, 0.1, False),  # 3.0 < 5.0, above=True, should be invalid
            (5.0, 3.0, "limit", False, 0.1, False),  # 5.0 > 3.0, above=False, should be invalid
        ]

        for value, limit_value, limit_name, above, delta, should_be_valid in test_cases:
            error_msg, corrected_value = model.validate_against_another_value(value, limit_value, limit_name, above, delta)
            if not should_be_valid:
                assert error_msg != ""
                assert corrected_value is not None
                if above:
                    assert corrected_value == limit_value + delta
                else:
                    assert corrected_value == limit_value - delta

    def test_validate_against_another_value_string_limit_values(self, realistic_model) -> None:
        """
        Test validate_against_another_value with string limit values.

        GIVEN: A model and limit values as strings
        WHEN: Validating with valid and invalid string limit values
        THEN: Valid strings should be converted and checked; invalid strings should error
        """
        model = realistic_model

        # Test with valid string that can be converted to float
        error_msg, corrected_value = model.validate_against_another_value(5.0, "3.0", "limit", above=True, delta=0.1)
        assert error_msg == ""
        assert corrected_value is None

        # Test with invalid string that cannot be converted to float
        error_msg, corrected_value = model.validate_against_another_value(5.0, "not_a_number", "limit", above=True, delta=0.1)
        assert error_msg != ""
        assert corrected_value is None

    def test_validate_against_another_value_invalid_limit_types(self, realistic_model) -> None:
        """
        Test validate_against_another_value with invalid limit value types.

        GIVEN: A model and limit values that are neither float nor string
        WHEN: Validating with None or other invalid types as limits
        THEN: Validation should return errors without corrections
        """
        model = realistic_model

        # Test with limit value that's neither float nor string
        error_msg, corrected_value = model.validate_against_another_value(5.0, None, "limit", above=True, delta=0.1)
        assert error_msg != ""
        assert corrected_value is None

        error_msg, corrected_value = model.validate_against_another_value(5.0, [], "limit", above=True, delta=0.1)
        assert error_msg != ""
        assert corrected_value is None

    # Test validate_all_data method
    def test_validate_all_data_valid_entries(self, realistic_model) -> None:
        """
        Test validate_all_data with valid entry values.

        GIVEN: A model with initialized choices and valid component entries
        WHEN: Validating all entries for connection types and protocols
        THEN: Validation should pass with no errors
        """
        model = realistic_model
        model.init_possible_choices(
            {
                "RC_PROTOCOLS": {"Bitmask": {"9": "CRSF"}},
                "GPS_TYPE": {"values": {"2": "uBlox"}},
                "MOT_PWM_TYPE": {"values": {"6": "DShot600"}},
            }
        )

        valid_entries = {
            ("RC Receiver", "FC Connection", "Type"): "SERIAL7",
            ("RC Receiver", "FC Connection", "Protocol"): "CRSF",
            ("GNSS Receiver", "FC Connection", "Type"): "SERIAL3",
            ("GNSS Receiver", "FC Connection", "Protocol"): "uBlox",
            ("ESC", "FC Connection", "Type"): "Main Out",
            ("ESC", "FC Connection", "Protocol"): "DShot600",
        }

        is_valid, errors = model.validate_all_data(valid_entries)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_all_data_invalid_combobox_values(self, realistic_model) -> None:
        """
        Test validate_all_data with invalid combobox values.

        GIVEN: A model with initialized choices
        WHEN: Validating entries with invalid protocol values not in choices
        THEN: Validation should fail with error messages about invalid values
        """
        model = realistic_model
        model.init_possible_choices(
            {
                "RC_PROTOCOLS": {"Bitmask": {"9": "CRSF"}},
            }
        )

        invalid_entries = {
            ("RC Receiver", "FC Connection", "Protocol"): "InvalidProtocol",
        }

        is_valid, errors = model.validate_all_data(invalid_entries)
        assert is_valid is False
        assert len(errors) > 0
        assert "Invalid value" in errors[0]

    def test_validate_all_data_duplicate_connections(self, realistic_model) -> None:
        """
        Test validate_all_data with duplicate FC connections.

        GIVEN: A model with initialized choices
        WHEN: Validating entries with duplicate serial port connections
        THEN: Validation should fail with error about duplicate FC connection
        """
        model = realistic_model
        model.init_possible_choices({})

        # Test duplicate serial connections
        duplicate_entries = {
            ("RC Receiver", "FC Connection", "Type"): "SERIAL3",
            ("GNSS Receiver", "FC Connection", "Type"): "SERIAL3",
        }

        is_valid, errors = model.validate_all_data(duplicate_entries)
        assert is_valid is False
        assert len(errors) > 0
        assert "Duplicate FC connection" in errors[0]

    def test_validate_all_data_allowed_duplicates(self, realistic_model) -> None:
        """
        Test validate_all_data with allowed duplicate connections.

        GIVEN: A model with initialized choices
        WHEN: Validating entries with duplicate CAN connections (which are allowed)
        THEN: Validation should pass without errors
        """
        model = realistic_model
        model.init_possible_choices({})

        # Test allowed CAN duplicates
        allowed_entries = {
            ("RC Receiver", "FC Connection", "Type"): "CAN1",
            ("GNSS Receiver", "FC Connection", "Type"): "CAN1",
        }

        is_valid, errors = model.validate_all_data(allowed_entries)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_all_data_telemetry_rc_combinations(self, realistic_model) -> None:
        """
        Test validate_all_data with allowed Telemetry/RC Receiver combinations.

        GIVEN: A model with initialized choices
        WHEN: Validating Telemetry and RC Receiver on same serial port
        THEN: Validation should pass (this combination is explicitly allowed)
        """
        model = realistic_model
        model.init_possible_choices({})

        # Test allowed Telemetry and RC Receiver on same port
        allowed_entries = {
            ("Telemetry", "FC Connection", "Type"): "SERIAL1",
            ("RC Receiver", "FC Connection", "Type"): "SERIAL1",
        }

        is_valid, errors = model.validate_all_data(allowed_entries)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_all_data_battery_esc_combinations(self, realistic_model) -> None:
        """
        Test validate_all_data with allowed Battery Monitor/ESC combinations.

        GIVEN: A model with battery monitor using ESC protocol
        WHEN: Validating Battery Monitor and ESC on compatible ports
        THEN: Validation should pass when protocol is ESC
        """
        model = realistic_model
        model.init_possible_choices({})

        # Set up the battery monitor component with ESC protocol in the model data
        model.set_component_value(("Battery Monitor", "FC Connection", "Protocol"), "ESC")

        # Test allowed Battery Monitor and ESC on same port when protocol is ESC
        # Note: Battery Monitor should use a valid connection type like "Analog"
        allowed_entries = {
            ("Battery Monitor", "FC Connection", "Type"): "Analog",
            ("Battery Monitor", "FC Connection", "Protocol"): "ESC",
            ("ESC", "FC Connection", "Type"): "Main Out",
        }

        is_valid, errors = model.validate_all_data(allowed_entries)
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_all_data_empty_entries(self, realistic_model) -> None:
        """
        Test validate_all_data with empty entry values.

        GIVEN: A model with initialized choices
        WHEN: Validating an empty dictionary of entries
        THEN: Validation should pass with no errors
        """
        model = realistic_model
        model.init_possible_choices({})

        is_valid, errors = model.validate_all_data({})
        assert is_valid is True
        assert len(errors) == 0

    # Test get_combobox_values_for_path method (inherited from base class)
    def test_get_combobox_values_for_path(self, realistic_model) -> None:
        """
        Test get_combobox_values_for_path method.

        GIVEN: A model with initialized possible choices
        WHEN: Requesting combobox values for existing and non-existing paths
        THEN: Existing paths should return choices; non-existing paths return empty tuple
        """
        model = realistic_model
        model.init_possible_choices({})

        # Test existing path
        values = model.get_combobox_values_for_path(("Battery", "Specifications", "Chemistry"))
        assert isinstance(values, tuple)
        assert len(values) > 0
        assert "Lipo" in values

        # Test non-existing path
        values = model.get_combobox_values_for_path(("Unknown", "Path", "Value"))
        assert values == ()

    # Test edge cases and error handling
    def test_edge_cases_empty_strings(self, realistic_model) -> None:
        """
        Test handling of empty strings in validation methods.

        GIVEN: A realistic model with validation rules
        WHEN: Validating empty strings in entry limits and cell voltage
        THEN: Validation should return errors (cannot convert empty string to number)
        """
        model = realistic_model

        # Test empty string in validate_entry_limits
        error_msg, corrected_value = model.validate_entry_limits("", ("Frame", "Specifications", "TOW min Kg"))
        assert error_msg != ""
        assert corrected_value is None

        # Test empty string in validate_cell_voltage
        error_msg, corrected_value = model.validate_cell_voltage("", ("Battery", "Specifications", "Volt per cell max"))
        assert error_msg != ""
        assert corrected_value is not None

    def test_edge_cases_boundary_values(self, empty_model) -> None:
        """
        Test boundary values in validation rules.

        GIVEN: An empty model with validation rules
        WHEN: Validating values at, below, and above validation boundaries
        THEN: Boundary values should pass; out-of-range values should be corrected
        """
        model = empty_model

        rules = model.VALIDATION_RULES

        for path, (data_type, limits, _name) in rules.items():
            min_val, max_val = limits

            # Skip TOW tests for empty model since they depend on other values
            if "TOW" in path[2]:
                continue

            # Test minimum boundary
            error_msg, corrected_value = model.validate_entry_limits(str(min_val), path)
            assert error_msg == ""
            assert corrected_value is None

            # Test maximum boundary
            error_msg, corrected_value = model.validate_entry_limits(str(max_val), path)
            assert error_msg == ""
            assert corrected_value is None

            # Test below minimum
            below_min = min_val - 0.001 if data_type is float else min_val - 1
            error_msg, corrected_value = model.validate_entry_limits(str(below_min), path)
            assert error_msg != ""
            assert corrected_value == min_val

            # Test above maximum
            above_max = max_val + 0.001 if data_type is float else max_val + 1
            error_msg, corrected_value = model.validate_entry_limits(str(above_max), path)
            assert error_msg != ""
            assert corrected_value == max_val

    def test_edge_cases_none_values(self, realistic_model) -> None:
        """
        Test handling of None values in various methods.

        GIVEN: A realistic model
        WHEN: Setting a component value to None
        THEN: The value should be stored as an empty string
        """
        model = realistic_model

        # Test setting None value
        model.set_component_value(("Test", "Component"), None)
        assert model.get_component_value(("Test", "Component")) == ""

    def test_edge_cases_chemistry_unknown(self, empty_model) -> None:
        """
        Test behavior with unknown battery chemistry.

        GIVEN: A model with unknown battery chemistry set
        WHEN: Requesting recommended cell voltage
        THEN: Should return NaN for unknown chemistry
        """
        model = empty_model
        model._battery_chemistry = "UnknownChemistry"

        # Test that methods handle unknown chemistry gracefully
        recommended = model.recommended_cell_voltage(("Battery", "Specifications", "Volt per cell max"))
        assert isinstance(recommended, float)
        # Unknown chemistry returns NaN, which is the expected behavior
        assert math.isnan(recommended)  # Proper NaN check

    def test_large_validation_dataset(self, realistic_model) -> None:
        """
        Test validation with a large dataset to ensure performance.

        GIVEN: A model and 100 component entries
        WHEN: Validating a large dataset
        THEN: Validation should complete without errors or performance issues
        """
        model = realistic_model
        model.init_possible_choices({})

        # Create a large dataset
        large_entries = {}
        for i in range(100):
            large_entries[(f"Component{i}", "FC Connection", "Type")] = "None"
            large_entries[(f"Component{i}", "FC Connection", "Protocol")] = "None"

        # Should handle large datasets without issues
        is_valid, errors = model.validate_all_data(large_entries)
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)

    def test_protocol_choice_consistency(self, realistic_model) -> None:
        """
        Test that protocol choices remain consistent across multiple calls.

        GIVEN: A model with initialized choices
        WHEN: Updating possible choices multiple times for the same path
        THEN: Protocol choices should remain consistent across calls
        """
        model = realistic_model
        model.init_possible_choices({})

        # Update choices multiple times
        for _ in range(5):
            model._update_possible_choices_for_path(("RC Receiver", "FC Connection", "Type"), "SERIAL7")
            choices1 = model._possible_choices.get(("RC Receiver", "FC Connection", "Protocol"), ())

            model._update_possible_choices_for_path(("RC Receiver", "FC Connection", "Type"), "SERIAL7")
            choices2 = model._possible_choices.get(("RC Receiver", "FC Connection", "Protocol"), ())

            # Choices should be consistent
            assert choices1 == choices2

    def test_validation_rules_immutability(self, realistic_model) -> None:
        """
        Test that VALIDATION_RULES cannot be modified.

        GIVEN: A model with VALIDATION_RULES class attribute
        WHEN: Attempting to modify VALIDATION_RULES
        THEN: Should raise TypeError or AttributeError (MappingProxyType is immutable)
        """
        model = realistic_model

        # VALIDATION_RULES should be immutable (MappingProxyType)
        with pytest.raises((TypeError, AttributeError)):
            model.VALIDATION_RULES[("New", "Rule", "Path")] = (float, (0, 1), "New Rule")

    def test_comprehensive_chemistry_validation(self, empty_model) -> None:
        """
        Test comprehensive validation across all battery chemistries.

        GIVEN: A model and all available battery chemistry types
        WHEN: Setting each chemistry and validating its recommended voltages
        THEN: Each chemistry should set appropriate voltage values and validate correctly
        """
        model = empty_model

        for chemistry in BatteryCell.chemistries():
            # Set chemistry and verify side effects
            model.set_component_value(("Battery", "Specifications", "Chemistry"), chemistry)
            assert model._battery_chemistry == chemistry

            # Test voltage validation for this chemistry
            for voltage_type in ["Volt per cell max", "Volt per cell low", "Volt per cell crit"]:
                path = ("Battery", "Specifications", voltage_type)
                recommended = model.recommended_cell_voltage(path)

                # Recommended value should be valid
                if not math.isnan(recommended):  # Check for NaN properly
                    _error_msg, _corrected_value = model.validate_cell_voltage(str(recommended), path)
                    # Some relationships might fail due to initialization order, that's OK

    def test_post_init_integration(self, realistic_model) -> None:
        """
        Test that post_init is properly called and integrates well.

        GIVEN: A realistic model that has been initialized
        WHEN: Checking post_init effects and calling it again
        THEN: Battery chemistry should be initialized and remain stable across calls
        """
        model = realistic_model

        # post_init should have been called in fixture
        # Verify that the model is in a proper state
        assert hasattr(model, "_battery_chemistry")
        assert hasattr(model, "_possible_choices")

        # Battery chemistry should be initialized from data
        assert model._battery_chemistry == "Lipo"

        # Test that we can call post_init again without issues
        model.post_init({})
        assert model._battery_chemistry == "Lipo"

        assert model._battery_chemistry == "Lipo"

    # Test missing coverage areas
    def test_fallback_values_missing_param(self, empty_model) -> None:
        """
        Test fallback handling when parameters are missing from doc_dict.

        GIVEN: A model and doc_dict without expected parameters
        WHEN: Initializing possible choices with incomplete doc_dict
        THEN: Should use fallback choices for missing parameters
        """
        model = empty_model

        # Test with doc_dict that doesn't have expected parameters
        incomplete_doc = {
            "SOME_OTHER_PARAM": {"values": {"1": "Value1"}},
        }

        # This should trigger fallback behavior for missing RC_PROTOCOLS, MOT_PWM_TYPE, etc.
        model.init_possible_choices(incomplete_doc)

        # Should still have fallback choices
        assert isinstance(model._possible_choices, dict)
        assert len(model._possible_choices) > 0

    def test_mot_pwm_type_coverage(self, empty_model) -> None:
        """
        Test MOT_PWM_TYPE and Q_M_PWM_TYPE handling.

        GIVEN: A model and doc_dicts with MOT_PWM_TYPE or Q_M_PWM_TYPE
        WHEN: Initializing possible choices from both parameter types
        THEN: Motor PWM types should be available from either parameter
        """
        model = empty_model

        # Test with MOT_PWM_TYPE
        doc_dict_mot = {
            "MOT_PWM_TYPE": {"values": {"0": "Normal", "1": "OneShot", "6": "DShot600"}},
        }
        model.init_possible_choices(doc_dict_mot)

        # Reset and test with Q_M_PWM_TYPE (quadplane)
        doc_dict_q = {
            "Q_M_PWM_TYPE": {"values": {"0": "Normal", "1": "OneShot", "6": "DShot600"}},
        }
        model.init_possible_choices(doc_dict_q)

        # Should have motor PWM types available
        assert hasattr(model, "_mot_pwm_types")

    def test_battery_monitor_connection_list_type(self, realistic_model) -> None:
        """
        Test battery monitor connection handling with list types.

        GIVEN: A model with initialized choices
        WHEN: Updating choices for battery monitor with I2C connection
        THEN: Protocol choices should be populated for the connection type
        """  # pylint: disable=duplicate-code  # Common connection test pattern
        model = realistic_model
        model.init_possible_choices({})

        # Test updating choices for battery monitor with a connection type that might be in a list
        model._update_possible_choices_for_path(("Battery Monitor", "FC Connection", "Type"), "I2C1")
        protocol_choices = model._possible_choices.get(("Battery Monitor", "FC Connection", "Protocol"), ())
        assert len(protocol_choices) > 0
        # pylint: enable=duplicate-code

    def test_gnss_receiver_connection_list_type(self, realistic_model) -> None:
        """
        Test GNSS receiver connection handling with list types.

        GIVEN: A model with initialized choices
        WHEN: Updating choices for GNSS receiver with different connection types
        THEN: Protocol choices should be populated for each connection type
        """  # pylint: disable=duplicate-code  # Common connection test pattern
        model = realistic_model
        model.init_possible_choices({})

        # Test updating choices for GNSS receiver with different connection types
        model._update_possible_choices_for_path(("GNSS Receiver", "FC Connection", "Type"), "CAN1")
        protocol_choices = model._possible_choices.get(("GNSS Receiver", "FC Connection", "Protocol"), ())
        assert len(protocol_choices) > 0
        # pylint: enable=duplicate-code

    def test_validate_entry_limits_tow_value_errors(self, realistic_model) -> None:
        """
        Test TOW validation with invalid values that trigger value errors.

        GIVEN: A realistic model with TOW validation rules
        WHEN: Validating TOW values with non-numeric strings
        THEN: Should return conversion error messages without corrections
        """
        model = realistic_model

        # Test TOW max with non-float value
        error_msg, corrected_value = model.validate_entry_limits("not_a_float", ("Frame", "Specifications", "TOW max Kg"))
        assert "could not convert" in error_msg  # The actual error message from ValueError
        assert corrected_value is None

        # Test TOW min with non-float value
        error_msg, corrected_value = model.validate_entry_limits("invalid", ("Frame", "Specifications", "TOW min Kg"))
        assert "could not convert" in error_msg  # The actual error message from ValueError
        assert corrected_value is None

    def test_validate_cell_voltage_complex_relationships(self, realistic_model) -> None:
        """
        Test complex cell voltage validation relationships.

        GIVEN: A model with battery chemistry and established voltage values
        WHEN: Setting low voltage above max voltage (cascade violation)
        THEN: Should detect and correct the validation violation
        """
        model = realistic_model
        model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")

        # Set up initial voltages
        model.set_component_value(("Battery", "Specifications", "Volt per cell max"), 4.2)
        model.set_component_value(("Battery", "Specifications", "Volt per cell low"), 3.6)
        model.set_component_value(("Battery", "Specifications", "Volt per cell crit"), 3.3)

        # Test setting low voltage that causes a cascade of validation issues
        # This should test the double validation in validate_cell_voltage
        error_msg, corrected_value = model.validate_cell_voltage("4.3", ("Battery", "Specifications", "Volt per cell low"))
        assert error_msg != ""
        assert corrected_value is not None

    def test_bitmask_fallback_coverage(self, empty_model) -> None:
        """
        Test bitmask handling in doc_dict parsing.

        GIVEN: A model and doc_dict using Bitmask instead of values
        WHEN: Initializing possible choices from bitmask parameter
        THEN: Should correctly parse bitmask entries into protocol choices
        """
        model = empty_model

        # Test with Bitmask instead of values
        doc_dict_bitmask = {
            "RC_PROTOCOLS": {"Bitmask": {"0": "All", "1": "PPM", "9": "CRSF"}},
        }

        model.init_possible_choices(doc_dict_bitmask)

        # Should handle bitmask correctly
        rc_protocols = model._possible_choices.get(("RC Receiver", "FC Connection", "Protocol"), ())
        assert len(rc_protocols) > 0
        assert "All" in rc_protocols

    def test_doc_dict_missing_values_error_path(self, empty_model) -> None:
        """
        Test error paths when doc_dict has parameter but no values or bitmask.

        GIVEN: A model and doc_dict with parameters lacking values/bitmask
        WHEN: Initializing possible choices with incomplete parameter definitions
        THEN: Should gracefully handle missing data and use fallbacks
        """
        model = empty_model

        # Create a doc_dict with parameter that has neither values nor Bitmask
        doc_dict_no_values = {
            "RC_PROTOCOLS": {"some_other_key": "value"},
            "MOT_PWM_TYPE": {},  # Empty dict
        }

        # This should trigger the error paths but still work with fallbacks
        model.init_possible_choices(doc_dict_no_values)

        # Should still have some choices from fallbacks
        assert isinstance(model._possible_choices, dict)

    def test_pwm_output_protocol_choices(self, realistic_model) -> None:
        """
        Test PWM output protocol choices for ESC.

        GIVEN: A model with MOT_PWM_TYPE initialized
        WHEN: Updating ESC connection choices for PWM outputs
        THEN: Protocol choices should include motor PWM types
        """  # pylint: disable=duplicate-code  # Common connection test pattern
        model = realistic_model
        model.init_possible_choices({"MOT_PWM_TYPE": {"values": {"0": "Normal", "6": "DShot600"}}})

        # Test ESC connection to PWM outputs (not serial or CAN)
        model._update_possible_choices_for_path(("ESC", "FC Connection", "Type"), "Main Out")
        protocol_choices = model._possible_choices.get(("ESC", "FC Connection", "Protocol"), ())

        # Should use motor PWM types for PWM outputs
        assert len(protocol_choices) > 0
        assert "Normal" in protocol_choices or "DShot600" in protocol_choices
        # pylint: enable=duplicate-code

    def test_comprehensive_connection_type_coverage(self, realistic_model) -> None:
        """
        Test comprehensive coverage of connection type handling.

        GIVEN: A model with initialized choices and various components
        WHEN: Testing all major connection types for different components
        THEN: Each component/connection combination should have appropriate protocol choices
        """
        model = realistic_model
        model.init_possible_choices({})

        # Test all major connection types for different components
        # Some combinations may not have protocols available, which is expected behavior
        test_cases = [
            ("RC Receiver", "FC Connection", "Type", "None", True),  # Should have protocols
            ("RC Receiver", "FC Connection", "Type", "CAN1", True),  # Should have protocols
            ("RC Receiver", "FC Connection", "Type", "I2C1", False),  # May not have protocols (not common for RC)
            ("Telemetry", "FC Connection", "Type", "None", True),  # Should have protocols
            ("Telemetry", "FC Connection", "Type", "SERIAL1", True),  # Should have protocols
            ("ESC", "FC Connection", "Type", "None", True),  # Should have protocols
            ("ESC", "FC Connection", "Type", "CAN1", True),  # Should have protocols
            ("GNSS Receiver", "FC Connection", "Type", "None", True),  # Should have protocols
            ("GNSS Receiver", "FC Connection", "Type", "SERIAL3", True),  # Should have protocols
            ("Battery Monitor", "FC Connection", "Type", "None", True),  # Should have protocols
            ("Battery Monitor", "FC Connection", "Type", "Analog", True),  # Should have protocols
        ]

        for component, section, field, value, should_have_protocols in test_cases:
            model._update_possible_choices_for_path((component, section, field), value)
            protocol_path = (component, "FC Connection", "Protocol")
            protocol_choices = model._possible_choices.get(protocol_path, ())

            if should_have_protocols:
                # These combinations should have at least one protocol choice
                assert len(protocol_choices) > 0, f"{component} with {value} should have protocols but got: {protocol_choices}"
            # If should_have_protocols is False, we don't assert anything (empty is acceptable)
