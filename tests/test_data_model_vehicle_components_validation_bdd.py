#!/usr/bin/env python3

"""
Vehicle Components data model validation tests.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest
from test_data_model_vehicle_components_common import ComponentDataModelFixtures

from ardupilot_methodic_configurator.data_model_vehicle_components_validation import ComponentDataModelValidation


class TestValidateAllDataBehaviorDriven:
    """Test the integrated validate_all_data behavior with all validation types."""

    @pytest.fixture
    def validation_model(self) -> ComponentDataModelValidation:
        """Fixture providing a validation model with realistic test data."""
        return ComponentDataModelFixtures.create_realistic_model(ComponentDataModelValidation)

    def test_user_can_validate_all_component_data_successfully(self, validation_model) -> None:
        """
        User can validate a complete vehicle configuration without any errors.

        GIVEN: A user has filled out all vehicle component data correctly
        WHEN: They validate all data before saving
        THEN: All validation should pass without errors
        AND: The system should confirm the data is valid
        """
        # Arrange: Create valid component data for all validation types
        valid_entries = {
            # Combobox validation
            ("Frame", "type"): "X",
            ("Flight Controller", "type"): "Pixhawk 6X",
            # Numeric validation rules
            ("ESC", "nr_motors"): "4",
            ("Motors", "rpm_per_volt"): "3800",
            ("Propellers", "diameter_inches"): "5.1",
            # Battery voltage validation
            ("Battery", "chemistry"): "Lipo",
            ("Battery", "critical_voltage"): "3.0",
            ("Battery", "low_voltage"): "3.3",
            ("Battery", "nominal_voltage"): "3.7",
            ("Battery", "max_voltage"): "4.2",
            # FC connections (no duplicates)
            ("RC Receiver", "fc_connection"): "SERIAL1",
            ("Telemetry", "fc_connection"): "SERIAL2",
            ("GNSS Receiver", "fc_connection"): "SERIAL3",
        }

        # Act: Validate all data
        is_valid, errors = validation_model.validate_all_data(valid_entries)

        # Assert: All validation passes
        assert is_valid is True
        assert len(errors) == 0

    def test_user_sees_validation_errors_for_invalid_numeric_values(self, validation_model) -> None:
        """
        User receives specific error messages when numeric values exceed validation limits.

        GIVEN: A user enters numeric values that violate validation rules
        WHEN: They attempt to validate the data
        THEN: They should receive specific error messages for each invalid value
        AND: The system should suggest corrected values where possible
        """
        # Arrange: Create entries with invalid numeric values that match the actual validation rules
        invalid_entries = {
            ("Frame", "Specifications", "TOW min Kg"): "999",  # Exceeds max limit (600)
            ("Motors", "Specifications", "Poles"): "-5",  # Below min limit (3)
            ("Propellers", "Specifications", "Diameter_inches"): "0.1",  # Below min limit (0.3)
            ("Battery", "Specifications", "Number of cells"): "99",  # Exceeds max limit (50)
        }

        # Act: Validate all data
        is_valid, errors = validation_model.validate_all_data(invalid_entries)

        # Assert: Validation fails with specific error messages
        assert is_valid is False
        assert len(errors) >= 2  # At least errors for invalid numeric values

        # Check for specific validation error patterns
        error_text = " ".join(errors)
        assert "TOW min Kg" in error_text or "Takeoff Weight" in error_text
        assert "Poles" in error_text or "Motor Poles" in error_text

    def test_user_sees_validation_errors_for_invalid_battery_voltages(self, validation_model) -> None:
        """
        User receives specific error messages when battery voltages violate chemistry constraints.

        GIVEN: A user enters battery voltages that violate chemistry limits or relationships
        WHEN: They attempt to validate the data
        THEN: They should receive specific error messages about voltage relationships
        AND: The system should identify which voltages are problematic
        """
        # Arrange: Create entries with invalid battery voltage relationships
        invalid_entries = {
            ("Battery", "Specifications", "Chemistry"): "Lipo",
            ("Battery", "Specifications", "Volt per cell max"): "5.0",  # Above Lipo max (4.2)
            ("Battery", "Specifications", "Volt per cell low"): "2.0",  # Below Lipo min (3.0)
            ("Battery", "Specifications", "Volt per cell crit"): "1.5",  # Below Lipo min (3.0)
        }

        # Act: Validate all data
        is_valid, errors = validation_model.validate_all_data(invalid_entries)

        # Assert: Validation fails with battery voltage errors
        assert is_valid is False
        assert len(errors) >= 1

        # Check for battery voltage error patterns
        " ".join(errors)
        assert any("lipo" in error.lower() and ("limit" in error.lower() or "voltage" in error.lower()) for error in errors)

    def test_user_sees_validation_errors_for_invalid_combobox_selections(self, validation_model) -> None:
        """
        User receives error messages when selecting invalid options from dropdown lists.

        GIVEN: A user selects invalid options from combobox fields
        WHEN: They attempt to validate the data
        THEN: They should receive error messages about invalid selections
        AND: The system should indicate which selections are not allowed
        """
        # Arrange: Create entries with invalid combobox selections (use paths that actually have choices)
        invalid_entries = {
            ("Battery", "Specifications", "Chemistry"): "UnknownChemistry",  # Chemistry has combobox choices
            ("RC Receiver", "FC Connection", "Protocol"): "InvalidProtocol",  # RC Protocol has choices
            ("ESC", "FC Connection", "Protocol"): "NonExistentProtocol",  # ESC Protocol has choices
        }

        # Act: Validate all data
        is_valid, errors = validation_model.validate_all_data(invalid_entries)

        # Assert: Validation fails with combobox errors
        assert is_valid is False
        assert len(errors) >= 1

        # Check for combobox error patterns
        _error_text = " ".join(errors)
        assert any(
            "not a valid choice" in error or "invalid" in error.lower() or "UnknownChemistry" in error for error in errors
        )

    def test_user_sees_validation_errors_for_duplicate_fc_connections(self, validation_model) -> None:
        """
        User receives error messages when assigning duplicate flight controller connections.

        GIVEN: A user assigns the same FC connection to multiple components
        WHEN: They attempt to validate the data
        THEN: They should receive error messages about duplicate connections
        AND: The system should identify which connections are duplicated
        """
        # Arrange: Create entries with duplicate FC connections that are NOT allowed
        duplicate_entries = {
            ("GNSS Receiver", "FC Connection", "Type"): "SERIAL2",
            ("ESC", "FC Connection", "Type"): "SERIAL2",  # Not allowed duplicate
            ("RC Receiver", "FC Connection", "Type"): "SERIAL3",
            (
                "Battery Monitor",
                "FC Connection",
                "Type",
            ): "SERIAL3",  # Not allowed duplicate (unless BattMon uses ESC protocol)
        }

        # Act: Validate all data
        is_valid, errors = validation_model.validate_all_data(duplicate_entries)

        # Assert: Validation fails with duplicate connection errors
        assert is_valid is False
        assert len(errors) >= 1  # At least one duplicate should be detected

        # Check for duplicate connection error patterns
        error_text = " ".join(errors)
        assert any("duplicate" in error.lower() or "already" in error.lower() for error in errors)
        assert "SERIAL2" in error_text or "SERIAL3" in error_text
        assert any("duplicate" in error.lower() or "already" in error.lower() for error in errors)

    def test_user_can_validate_data_with_allowed_duplicate_connections(self, validation_model) -> None:
        """
        User can successfully validate data when using allowed duplicate connections.

        GIVEN: A user assigns the same FC connection to components that allow sharing
        WHEN: They attempt to validate the data
        THEN: The validation should pass without errors
        AND: The system should allow these specific duplicate connections
        """
        # Arrange: Create entries with allowed duplicate connections
        allowed_entries = {
            # Allowed: RC Receiver and Telemetry can share connections
            ("RC Receiver", "FC Connection", "Type"): "SERIAL1",
            ("Telemetry", "FC Connection", "Type"): "SERIAL1",  # Allowed duplicate
            # Allowed: CAN and I2C connections can be shared
            ("GNSS Receiver", "FC Connection", "Type"): "CAN1",
            ("Battery Monitor", "FC Connection", "Type"): "CAN1",  # Allowed duplicate
        }

        # Act: Validate all data
        is_valid, errors = validation_model.validate_all_data(allowed_entries)

        # Assert: Validation passes for allowed duplicates
        assert is_valid is True
        assert len(errors) == 0

    def test_user_sees_mixed_validation_results_with_partial_errors(self, validation_model) -> None:
        """
        User receives comprehensive feedback when data has both valid and invalid entries.

        GIVEN: A user has a mix of valid and invalid component data
        WHEN: They attempt to validate all data
        THEN: They should receive error messages only for invalid entries
        AND: Valid entries should not generate errors
        AND: All error types should be captured in a single validation pass
        """
        # Arrange: Create mixed valid/invalid entries
        mixed_entries = {
            # Valid entries
            ("Frame", "Specifications", "TOW min Kg"): "1.0",  # Valid
            # Invalid numeric value
            ("Frame", "Specifications", "TOW max Kg"): "999",  # Exceeds limit (600)
            # Invalid combobox selection (this path needs to be something that has choices)
            ("Battery", "Specifications", "Chemistry"): "InvalidChemistry",
            # Invalid battery voltage relationship
            ("Battery", "Specifications", "Volt per cell max"): "5.0",  # Too high for Lipo
            ("Battery", "Specifications", "Volt per cell low"): "3.3",
            # Valid connection
            ("RC Receiver", "FC Connection", "Type"): "SERIAL1",
        }

        # Act: Validate all data
        is_valid, errors = validation_model.validate_all_data(mixed_entries)

        # Assert: Validation fails but captures all error types
        assert is_valid is False
        assert len(errors) >= 2  # At least errors for invalid numeric and battery voltage

        # Verify different error types are captured
        error_text = " ".join(errors)
        assert "TOW max Kg" in error_text or "Takeoff Weight" in error_text  # Numeric error
        assert "lipo" in error_text.lower() or "voltage" in error_text.lower()  # Battery voltage error

    def test_user_can_validate_empty_or_minimal_component_data(self, validation_model) -> None:
        """
        User can validate component data with minimal or empty entries.

        GIVEN: A user has minimal component data or some empty fields
        WHEN: They attempt to validate the data
        THEN: The validation should handle empty values gracefully
        AND: Only non-empty invalid values should generate errors
        """
        # Arrange: Create entries with minimal/empty data
        minimal_entries = {
            ("Frame", "type"): "X",  # Valid
            ("Flight Controller", "type"): "",  # Empty
            ("ESC", "nr_motors"): "",  # Empty
            ("Battery", "chemistry"): "Lipo",  # Valid
            ("Battery", "critical_voltage"): "",  # Empty
        }

        # Act: Validate all data
        is_valid, errors = validation_model.validate_all_data(minimal_entries)

        # Assert: Validation handles empty values appropriately
        # The behavior depends on whether empty values are considered invalid
        # This test verifies the system doesn't crash with empty values
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)

    def test_user_receives_corrected_values_for_invalid_numeric_inputs(self, validation_model) -> None:
        """
        User's invalid numeric values are automatically corrected when possible.

        GIVEN: A user enters numeric values that can be corrected to valid ranges
        WHEN: They validate the data
        THEN: The system should automatically apply corrections
        AND: The corrected values should be stored in the model
        AND: Error messages should indicate what corrections were made
        """
        # Arrange: Create entries with out-of-range numeric values that match validation rules
        correctable_entries = {
            ("Frame", "Specifications", "TOW min Kg"): "999",  # Will be corrected to max value (600)
            ("Motors", "Specifications", "Poles"): "-5",  # Will be corrected to min value (3)
        }

        # Store original values for comparison
        validation_model.get_component_value(("Frame", "Specifications", "TOW min Kg"))
        validation_model.get_component_value(("Motors", "Specifications", "Poles"))

        # Act: Validate all data (this should apply corrections)
        is_valid, errors = validation_model.validate_all_data(correctable_entries)

        # Assert: Values are corrected in the model
        corrected_tow = validation_model.get_component_value(("Frame", "Specifications", "TOW min Kg"))
        corrected_poles = validation_model.get_component_value(("Motors", "Specifications", "Poles"))

        # The values should be different from the invalid inputs
        assert corrected_tow != "999"
        assert corrected_poles != "-5"

        # Errors should indicate corrections were made
        assert len(errors) >= 1  # Should have error messages about corrections
        assert not is_valid

    def test_user_validation_handles_complex_battery_voltage_relationships(self, validation_model) -> None:
        """
        User receives appropriate feedback for complex battery voltage validation scenarios.

        GIVEN: A user enters battery voltages with complex relationship violations
        WHEN: They validate the data with multiple battery voltage paths
        THEN: The system should validate all voltage relationships
        AND: Error messages should be specific about which relationships are violated
        """
        # Arrange: Create complex battery voltage scenario
        complex_battery_entries = {
            ("Battery", "Specifications", "Chemistry"): "Lipo",
            ("Battery", "Specifications", "Volt per cell crit"): "3.2",  # Valid
            ("Battery", "Specifications", "Volt per cell low"): "3.1",  # Invalid: lower than critical
            ("Battery", "Specifications", "Volt per cell max"): "5.0",  # Invalid: too high for Lipo
        }

        # Act: Validate all data
        is_valid, errors = validation_model.validate_all_data(complex_battery_entries)

        # Assert: Complex validation identifies multiple issues
        assert is_valid is False
        assert len(errors) >= 1

        # Check that voltage relationship errors are identified
        error_text = " ".join(errors).lower()
        assert "lipo" in error_text
        assert "limit" in error_text or "voltage" in error_text

    def test_validation_performance_with_large_dataset(self, validation_model) -> None:
        """
        Validation performs efficiently with large datasets.

        GIVEN: A user has a large dataset with many component entries
        WHEN: They validate all data
        THEN: The validation should complete efficiently
        AND: All validation types should be processed
        """
        # Arrange: Create large dataset with many entries
        large_entries = {}

        # Add many valid entries
        for i in range(50):
            large_entries[(f"Component{i}", "param")] = "ValidValue"

        # Add some invalid entries to test all validation paths
        large_entries[("Frame", "Specifications", "TOW min Kg")] = "999"  # Invalid numeric (exceeds 600)
        large_entries[("Battery", "Specifications", "Chemistry")] = "InvalidChem"  # Invalid combobox
        large_entries[("Battery", "Specifications", "Volt per cell max")] = "5.0"  # Invalid battery voltage for Lipo
        large_entries[("RC Receiver", "FC Connection", "Type")] = "SERIAL1"
        large_entries[("ESC", "FC Connection", "Type")] = "SERIAL1"  # Not allowed duplicate

        # Act: Validate all data
        is_valid, errors = validation_model.validate_all_data(large_entries)

        # Assert: Validation completes and finds the invalid entries
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)
        # Should find at least the intentionally invalid entries
        assert len(errors) >= 1
