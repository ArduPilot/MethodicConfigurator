#!/usr/bin/env python3

"""
Vehicle Components data model templates interface tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest
from test_data_model_vehicle_components_common import BasicTestMixin, ComponentDataModelFixtures, RealisticDataTestMixin

from ardupilot_methodic_configurator.data_model_vehicle_components_base import ComponentDataModelBase
from ardupilot_methodic_configurator.data_model_vehicle_components_templates import ComponentDataModelTemplates

# pylint: disable=too-many-public-methods,too-many-lines


class TestComponentDataModelTemplates(BasicTestMixin, RealisticDataTestMixin):
    """Tests for the ComponentDataModelTemplates class."""

    @pytest.fixture
    def empty_model(self) -> ComponentDataModelTemplates:
        """Create an empty ComponentDataModelTemplates fixture for testing."""
        return ComponentDataModelFixtures.create_empty_model(ComponentDataModelTemplates)

    @pytest.fixture
    def basic_model(self) -> ComponentDataModelTemplates:
        """Create a ComponentDataModelTemplates fixture for testing."""
        return ComponentDataModelFixtures.create_basic_model(ComponentDataModelTemplates)

    @pytest.fixture
    def realistic_model(self) -> ComponentDataModelTemplates:
        """Create a realistic vehicle data model based on the JSON file."""
        return ComponentDataModelFixtures.create_realistic_model(ComponentDataModelTemplates)

    # Template-specific tests (inheritance test and template methods)
    def test_class_inherits_from_component_data_model(self, empty_model) -> None:
        """
        That ComponentDataModelTemplates inherits from ComponentDataModel.

        GIVEN: The VehicleComponentsTemplateData class
        WHEN: Checking its inheritance
        THEN: It should inherit from VehicleComponentsDataModel
        """
        assert isinstance(empty_model, ComponentDataModelBase)

    # Template-specific method tests

    def test_user_can_add_new_component(self, empty_model) -> None:
        """
        User can add a new component to the vehicle configuration.

        GIVEN: An empty component data model
        WHEN: The user adds a new component with data
        THEN: The component should be stored in the model
        AND: The component data should match the input exactly
        """
        component_name = "New Motor"
        component_data = {"Type": "servo", "Torque": 15}

        empty_model.update_component(component_name, component_data)

        assert "Components" in empty_model.get_component_data()
        assert component_name in empty_model.get_component_data()["Components"]
        assert empty_model.get_component_data()["Components"][component_name] == component_data

    def test_user_can_update_existing_component(self, basic_model) -> None:
        """
        User updating an existing component.

        GIVEN: A model with existing components
        WHEN: The user updates a component with new data
        THEN: The component should reflect the updated values
        """
        component_name = "Motor"
        new_component_data = {"Type": "stepper", "Steps": 200}

        basic_model.update_component(component_name, new_component_data)

        assert basic_model.get_component_data()["Components"][component_name] == new_component_data

    def test_system_creates_components_key_when_missing(self) -> None:
        """
        System updating component when Components key doesn't exist.

        GIVEN: Data without a Components key
        WHEN: The user adds a component
        THEN: The system should create the Components structure
        AND: The component should be added successfully
        """
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        data_without_components = {"Format version": 1}
        model = ComponentDataModelTemplates(data_without_components, component_datatypes, schema)
        model.post_init({})

        component_name = "Test Component"
        component_data = {"Test": "Value"}

        model.update_component(component_name, component_data)

        assert "Components" in model.get_component_data()
        assert component_name in model.get_component_data()["Components"]
        assert model.get_component_data()["Components"][component_name] == component_data

    def test_user_can_add_component_with_complex_nested_data(self, empty_model) -> None:
        """
        User updating component with complex nested data.

        GIVEN: An empty component model
        WHEN: The user adds a component with deeply nested data
        THEN: All nested data should be stored correctly
        AND: Data integrity should be maintained
        """
        component_name = "Complex Component"
        component_data = {
            "Product": {"Manufacturer": "Test Corp", "Model": "Model X", "Version": "2.0"},
            "Specifications": {"Power": 100, "Voltage": 12.5, "Features": ["Feature1", "Feature2"]},
            "Notes": "Test component for testing",
        }

        empty_model.update_component(component_name, component_data)

        stored_data = empty_model.get_component_data()["Components"][component_name]
        assert stored_data == component_data
        assert stored_data["Product"]["Manufacturer"] == "Test Corp"
        assert stored_data["Specifications"]["Features"] == ["Feature1", "Feature2"]

    def test_system_derives_template_name_from_product_info(self) -> None:
        """
        System deriving template name from component data with Product information.

        GIVEN: Component data with Product manufacturer and model
        WHEN: The system derives a template name
        THEN: It should combine manufacturer and model with a space
        """
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = ComponentDataModelTemplates({}, component_datatypes, schema)

        component_data = {"Product": {"Manufacturer": "Arduino", "Model": "Uno R3"}}

        result = model.derive_initial_template_name(component_data)
        assert result == "Arduino Uno R3"

    def test_system_derives_template_name_without_manufacturer(self) -> None:
        """
        System deriving template name when manufacturer is missing.

        GIVEN: Component data with model but no manufacturer
        WHEN: The system derives a template name
        THEN: It should use space + model
        """
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = ComponentDataModelTemplates({}, component_datatypes, schema)

        component_data = {"Product": {"Model": "Solo Model"}}

        result = model.derive_initial_template_name(component_data)
        assert result == " Solo Model"

    def test_system_derives_template_name_without_model(self) -> None:
        """
        System deriving template name when model is missing.

        GIVEN: Component data with manufacturer but no model
        WHEN: The system derives a template name
        THEN: It should use manufacturer + space
        """
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = ComponentDataModelTemplates({}, component_datatypes, schema)

        component_data = {"Product": {"Manufacturer": "Solo Manufacturer"}}

        result = model.derive_initial_template_name(component_data)
        assert result == "Solo Manufacturer "

    def test_system_returns_empty_name_without_product_data(self) -> None:
        """
        System deriving template name when Product data is missing.

        GIVEN: Component data without Product section
        WHEN: The system derives a template name
        THEN: It should return an empty string
        """
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = ComponentDataModelTemplates({}, component_datatypes, schema)

        component_data = {"Specifications": {"Power": 100}, "Notes": "No product info"}

        result = model.derive_initial_template_name(component_data)
        assert result == ""

    def test_system_handles_empty_product_data(self) -> None:
        """
        System deriving template name with empty Product data.

        GIVEN: Component data with empty Product dictionary
        WHEN: The system derives a template name
        THEN: It should return a string with single space
        """
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = ComponentDataModelTemplates({}, component_datatypes, schema)

        component_data = {"Product": {}}

        result = model.derive_initial_template_name(component_data)
        assert result == " "

    def test_system_handles_empty_component_data(self) -> None:
        """
        System deriving template name with completely empty component data.

        GIVEN: Completely empty component data
        WHEN: The system derives a template name
        THEN: It should return an empty string
        """
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = ComponentDataModelTemplates({}, component_datatypes, schema)

        result = model.derive_initial_template_name({})
        assert result == ""

    def test_system_preserves_special_characters_in_names(self) -> None:
        """
        System deriving template name with special characters in manufacturer and model.

        GIVEN: Component data with special characters in manufacturer and model
        WHEN: The system derives a template name
        THEN: It should preserve all special characters
        """
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = ComponentDataModelTemplates({}, component_datatypes, schema)

        component_data = {"Product": {"Manufacturer": "Manu-Corp™", "Model": "Model-X_v2.1"}}

        result = model.derive_initial_template_name(component_data)
        assert result == "Manu-Corp™ Model-X_v2.1"

    # Integration tests combining multiple methods
    def test_user_can_complete_full_component_configuration_workflow(self, empty_model) -> None:
        """
        User complete workflow from empty model to populated with template.

        GIVEN: An empty component model
        WHEN: The user configures template and adds multiple components
        THEN: All components should be stored with correct data
        AND: Template name should be set correctly
        """
        # Set configuration template
        template_name = "Custom Drone Template"
        empty_model.set_configuration_template(template_name)

        # Add multiple components
        motor_data = {"Product": {"Manufacturer": "T-Motor", "Model": "F80"}, "Specifications": {"KV": 2400}}
        esc_data = {"Product": {"Manufacturer": "BLHeli", "Model": "32bit ESC"}, "Specifications": {"Current": 40}}

        empty_model.update_component("Motor", motor_data)
        empty_model.update_component("ESC", esc_data)

        # Verify final state
        assert empty_model.get_component_data()["Configuration template"] == template_name
        assert "Motor" in empty_model.get_component_data()["Components"]
        assert "ESC" in empty_model.get_component_data()["Components"]
        assert empty_model.get_component_data()["Components"]["Motor"]["Product"]["Manufacturer"] == "T-Motor"

    def test_user_can_derive_and_use_template_name(self, empty_model) -> None:
        """
        User deriving template name and then setting it.

        GIVEN: Component data with manufacturer and model
        WHEN: The user derives a template name from the data
        THEN: The derived name should correctly combine manufacturer and model
        """
        component_data = {"Product": {"Manufacturer": "DJI", "Model": "Mavic Pro"}}

        # Derive template name
        derived_name = empty_model.derive_initial_template_name(component_data)
        assert derived_name == "DJI Mavic Pro"

    # Edge cases and error handling
    def test_user_can_set_component_to_none(self, empty_model) -> None:
        """
        User updating component with None data.

        GIVEN: An empty component model
        WHEN: The user sets a component to None
        THEN: The None value should be stored
        """
        empty_model.update_component("Test", None)
        assert empty_model.get_component_data()["Components"]["Test"] is None

    def test_system_raises_error_for_none_input(self) -> None:
        """
        System deriving template name with None input.

        GIVEN: None as input to template derivation
        WHEN: The system attempts to derive a template name
        THEN: It should raise an AttributeError
        """
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = ComponentDataModelTemplates({}, component_datatypes, schema)

        with pytest.raises(AttributeError):
            model.derive_initial_template_name(None)

    # Data persistence and retrieval tests
    def test_system_maintains_data_integrity_across_operations(self, basic_model) -> None:
        """
        System that data persists correctly after multiple operations.

        GIVEN: A model with existing components
        WHEN: The user performs multiple update operations
        THEN: Original unmodified components should remain unchanged
        AND: New components should be added correctly
        """
        original_battery_data = basic_model.get_component_data()["Components"]["Battery"].copy()

        # Perform various operations
        basic_model.update_component("New Component", {"Test": "Data"})

        # Verify original data is still intact
        assert basic_model.get_component_data()["Components"]["Battery"] == original_battery_data
        assert "New Component" in basic_model.get_component_data()["Components"]

    def test_system_isolates_component_updates(self, basic_model) -> None:
        """
        System that component data updates don't affect other components.

        GIVEN: A model with multiple components
        WHEN: The user updates one specific component
        THEN: Only that component should change
        AND: Other components should remain unaffected
        """
        original_battery_data = basic_model.get_component_data()["Components"]["Battery"].copy()

        # Update Frame component
        new_frame_data = {"Type": "updated", "Weight": 500}
        basic_model.update_component("Frame", new_frame_data)

        # Verify Battery data is unchanged
        assert basic_model.get_component_data()["Components"]["Battery"] == original_battery_data
        assert basic_model.get_component_data()["Components"]["Frame"] == new_frame_data

    # Realistic data tests
    def test_user_can_access_realistic_vehicle_components(self, realistic_model) -> None:
        """
        User access to realistic vehicle data.

        GIVEN: A realistic vehicle configuration
        WHEN: The user accesses component data
        THEN: All component data should be accessible
        AND: Data values should match the realistic configuration
        """
        assert "Flight Controller" in realistic_model.get_component_data()["Components"]
        assert "Frame" in realistic_model.get_component_data()["Components"]

        fc_data = realistic_model.get_component_data()["Components"]["Flight Controller"]
        assert fc_data["Product"]["Manufacturer"] == "Matek"
        assert fc_data["Product"]["Model"] == "H743 SLIM"

    def test_system_derives_templates_from_realistic_data(self, realistic_model) -> None:
        """
        System deriving template names from realistic component data.

        GIVEN: Realistic component data for multiple components
        WHEN: The system derives template names
        THEN: Template names should correctly reflect manufacturer and model
        """
        fc_data = realistic_model.get_component_data()["Components"]["Flight Controller"]
        derived_name = realistic_model.derive_initial_template_name(fc_data)
        assert derived_name == "Matek H743 SLIM"

        frame_data = realistic_model.get_component_data()["Components"]["Frame"]
        derived_name = realistic_model.derive_initial_template_name(frame_data)
        assert derived_name == "Diatone Taycan MX-C"

    def test_user_can_update_realistic_components(self, realistic_model) -> None:
        """
        User updating components in realistic data.

        GIVEN: A realistic vehicle configuration
        WHEN: The user updates a component with new data
        THEN: The component should be updated correctly
        """
        new_fc_data = {
            "Product": {"Manufacturer": "Pixhawk", "Model": "6C", "Version": "1.0"},
            "Notes": "Updated flight controller",
        }

        realistic_model.update_component("Flight Controller", new_fc_data)

        updated_data = realistic_model.get_component_data()["Components"]["Flight Controller"]
        assert updated_data == new_fc_data
        assert updated_data["Product"]["Manufacturer"] == "Pixhawk"

    # Validation and type checking tests
    def test_user_can_use_various_component_name_formats(self, empty_model) -> None:
        """
        User component names with different types.

        GIVEN: An empty component model
        WHEN: The user adds components with different name formats
        THEN: All name formats should be accepted and stored
        """
        # String component name (normal case)
        empty_model.update_component("String Name", {"data": "value"})
        assert "String Name" in empty_model.get_component_data()["Components"]

        # Component name with numbers
        empty_model.update_component("Motor1", {"data": "value"})
        assert "Motor1" in empty_model.get_component_data()["Components"]

        # Component name with special characters
        empty_model.update_component("Motor-2_v1", {"data": "value"})
        assert "Motor-2_v1" in empty_model.get_component_data()["Components"]

    def test_user_can_store_various_data_types(self, empty_model) -> None:
        """
        User component data with various types.

        GIVEN: An empty component model
        WHEN: The user adds components with different data types
        THEN: All data types should be stored correctly
        """
        # Dictionary data
        dict_data = {"key": "value", "nested": {"inner": "data"}}
        empty_model.update_component("Dict Component", dict_data)
        assert empty_model.get_component_data()["Components"]["Dict Component"] == dict_data

        # List data
        list_data = ["item1", "item2", {"nested": "in_list"}]
        empty_model.update_component("List Component", list_data)
        assert empty_model.get_component_data()["Components"]["List Component"] == list_data

        # Mixed types
        mixed_data = {
            "string": "text",
            "number": 42,
            "float": 3.14,
            "boolean": True,
            "list": [1, 2, 3],
            "dict": {"inner": "value"},
        }
        empty_model.update_component("Mixed Component", mixed_data)
        assert empty_model.get_component_data()["Components"]["Mixed Component"] == mixed_data

    # Performance and stress tests
    def test_system_handles_many_component_updates(self, empty_model) -> None:
        """
        System updating many components for performance.

        GIVEN: An empty component model
        WHEN: The user adds many components
        THEN: All components should be added successfully
        """
        num_components = 100

        # Account for default components that are automatically added (Battery, Frame, Flight Controller)
        initial_component_count = len(empty_model.get_component_data()["Components"])

        for i in range(num_components):
            component_name = f"Component_{i}"
            component_data = {
                "id": i,
                "data": f"data_{i}",
                "Product": {"Manufacturer": f"Manufacturer_{i}", "Model": f"Model_{i}"},
            }
            empty_model.update_component(component_name, component_data)

        # Verify all components were added (initial + new components)
        expected_total = initial_component_count + num_components
        assert len(empty_model.get_component_data()["Components"]) == expected_total
        assert "Component_0" in empty_model.get_component_data()["Components"]
        assert "Component_99" in empty_model.get_component_data()["Components"]

    def test_system_handles_large_component_data(self, empty_model) -> None:
        """
        System handling large component data.

        GIVEN: An empty component model
        WHEN: The user adds a component with large nested data
        THEN: All data should be stored correctly regardless of size
        """
        large_data = {
            "Product": {"Manufacturer": "Test", "Model": "Large"},
            "large_list": list(range(1000)),
            "large_dict": {f"key_{i}": f"value_{i}" for i in range(100)},
            "nested_structure": {"level1": {"level2": {"level3": {"data": "deep_nested_value"}}}},
        }

        empty_model.update_component("Large Component", large_data)

        stored_data = empty_model.get_component_data()["Components"]["Large Component"]
        assert len(stored_data["large_list"]) == 1000
        assert len(stored_data["large_dict"]) == 100
        assert stored_data["nested_structure"]["level1"]["level2"]["level3"]["data"] == "deep_nested_value"

    # Tests for extract_component_data_from_entries method
    def test_user_can_extract_basic_component_data(self, empty_model) -> None:
        """
        User basic extraction of component data from entries.

        GIVEN: Entry data for a component
        WHEN: The user extracts component data from entries
        THEN: Data should be organized into proper structure
        """
        entries = {
            ("Motor", "Product", "Manufacturer"): "T-Motor",
            ("Motor", "Product", "Model"): "F80 Pro",
            ("Motor", "Specifications", "KV"): "2400",
            ("Motor", "Specifications", "Power"): "500",
        }

        result = empty_model.extract_component_data_from_entries("Motor", entries)

        expected = {
            "Product": {"Manufacturer": "T-Motor", "Model": "F80 Pro"},
            "Specifications": {"KV": 2400, "Power": 500},
        }

        assert result == expected

    def test_user_can_extract_single_level_data(self, empty_model) -> None:
        """
        User extraction with single-level paths.

        GIVEN: Single-level entry paths
        WHEN: The user extracts component data
        THEN: Data should be extracted at the correct level
        """
        entries = {
            ("ESC", "Type"): "BLHeli_32",
            ("ESC", "Current"): "40",
            ("ESC", "Voltage"): "6S",
        }

        result = empty_model.extract_component_data_from_entries("ESC", entries)

        expected = {"Type": "BLHeli_32", "Current": 40, "Voltage": "6S"}
        assert result == expected

    def test_user_can_extract_deeply_nested_data(self, empty_model) -> None:
        """
        User extraction with deeply nested paths.

        GIVEN: Deeply nested entry paths
        WHEN: The user extracts component data
        THEN: All nested levels should be preserved correctly
        """
        entries = {
            ("GPS", "Product", "Manufacturer"): "uBlox",
            ("GPS", "Product", "Model"): "NEO-8M",
            ("GPS", "Settings", "Protocol", "UART"): "true",
            ("GPS", "Settings", "Protocol", "I2C"): "false",
            ("GPS", "Settings", "Frequency", "Update"): "10",
            ("GPS", "Calibration", "Offset", "X"): "0.5",
            ("GPS", "Calibration", "Offset", "Y"): "-0.3",
        }

        result = empty_model.extract_component_data_from_entries("GPS", entries)

        expected = {
            "Product": {"Manufacturer": "uBlox", "Model": "NEO-8M"},
            "Settings": {"Protocol": {"UART": "true", "I2C": "false"}, "Frequency": {"Update": 10}},
            "Calibration": {"Offset": {"X": 0.5, "Y": -0.3}},
        }
        assert result == expected

    def test_system_returns_empty_dict_for_empty_entries(self, empty_model) -> None:
        """
        System extraction with empty entries.

        GIVEN: Empty entry dictionary
        WHEN: The user attempts to extract component data
        THEN: An empty dictionary should be returned
        """
        result = empty_model.extract_component_data_from_entries("Motor", {})
        assert result == {}

    def test_system_returns_empty_dict_when_no_matches(self, empty_model) -> None:
        """
        System extraction when no entries match the component name.

        GIVEN: Entries for other components
        WHEN: The user extracts data for a non-existent component
        THEN: An empty dictionary should be returned
        """
        entries = {
            ("ESC", "Type"): "BLHeli_32",
            ("GPS", "Model"): "NEO-8M",
        }

        result = empty_model.extract_component_data_from_entries("Motor", entries)
        assert result == {}

    def test_user_can_extract_data_from_specific_component(self, empty_model) -> None:
        """
        User extraction filters correctly when multiple components are present.

        GIVEN: Entries containing multiple components
        WHEN: The user extracts data for one specific component
        THEN: Only that component's data should be extracted
        """
        entries = {
            ("Motor", "Type"): "Brushless",
            ("Motor", "KV"): "2400",
            ("ESC", "Type"): "BLHeli_32",
            ("ESC", "Current"): "40",
            ("Battery", "Cells"): "4",
        }

        motor_result = empty_model.extract_component_data_from_entries("Motor", entries)
        esc_result = empty_model.extract_component_data_from_entries("ESC", entries)

        assert motor_result == {"Type": "Brushless", "KV": 2400}
        assert esc_result == {"Type": "BLHeli_32", "Current": 40}

    def test_system_converts_values_to_correct_types(self, empty_model) -> None:
        """
        System that values are properly converted based on datatypes.

        GIVEN: Entry values as strings
        WHEN: The system extracts and converts data
        THEN: Values should be converted to appropriate types based on schema
        """
        entries = {
            ("Battery", "Specifications", "Voltage"): "14.8",
            ("Battery", "Specifications", "Capacity"): "5200",
            ("Battery", "Specifications", "Chemistry"): "LiPo",
            ("Battery", "Specifications", "Discharge"): "25",
        }

        result = empty_model.extract_component_data_from_entries("Battery", entries)

        # Verify types are correctly converted
        assert result["Specifications"]["Voltage"] == 14.8  # float
        assert result["Specifications"]["Capacity"] == 5200  # int
        assert result["Specifications"]["Chemistry"] == "LiPo"  # string
        assert result["Specifications"]["Discharge"] == 25  # int

    def test_system_trims_whitespace_from_values(self, empty_model) -> None:
        """
        System extraction handles whitespace correctly.

        GIVEN: Entry values with whitespace
        WHEN: The system extracts component data
        THEN: Whitespace should be trimmed from values
        """
        entries = {
            ("Motor", "Product", "Manufacturer"): "  T-Motor  ",
            ("Motor", "Product", "Model"): "\tF80 Pro\n",
            ("Motor", "Notes"): "   High performance motor   ",
        }

        result = empty_model.extract_component_data_from_entries("Motor", entries)

        # Values should be trimmed
        assert result["Product"]["Manufacturer"] == "T-Motor"
        assert result["Product"]["Model"] == "F80 Pro"
        assert result["Notes"] == "High performance motor"

    def test_system_handles_scientific_notation(self, empty_model) -> None:
        """
        System extraction handles scientific notation in numeric values.

        GIVEN: Entry values in scientific notation
        WHEN: The system extracts component data
        THEN: Scientific notation should be converted to numeric values
        """
        entries = {
            ("Sensor", "Specifications", "Precision"): "1.5e-6",
            ("Sensor", "Specifications", "Range"): "1e3",
            ("Sensor", "Specifications", "Offset"): "-2.3e-2",
        }

        result = empty_model.extract_component_data_from_entries("Sensor", entries)

        assert result["Specifications"]["Precision"] == 1.5e-6
        assert result["Specifications"]["Range"] == 1000.0
        assert result["Specifications"]["Offset"] == -0.023

    def test_system_preserves_boolean_strings(self, empty_model) -> None:
        """
        System extraction handles boolean-like strings (they remain as strings without specific datatype).

        GIVEN: Entry values that look like booleans
        WHEN: The system extracts component data
        THEN: Boolean-like strings should be preserved as strings
        """
        entries = {
            ("Setting", "Feature", "Enabled"): "true",
            ("Setting", "Feature", "AutoMode"): "false",
            ("Setting", "Feature", "Debug"): "True",
            ("Setting", "Feature", "Logging"): "False",
        }

        result = empty_model.extract_component_data_from_entries("Setting", entries)

        # Values remain as strings since there's no specific boolean datatype defined for these paths
        assert result["Feature"]["Enabled"] == "true"
        assert result["Feature"]["AutoMode"] == "false"
        assert result["Feature"]["Debug"] == "True"
        assert result["Feature"]["Logging"] == "False"

    # Edge cases for extract_component_data_from_entries
    def test_system_handles_invalid_entry_paths_gracefully(self, empty_model) -> None:
        """
        System extraction handles invalid or malformed paths gracefully.

        GIVEN: Malformed or invalid entry paths
        WHEN: The system extracts component data
        THEN: Invalid paths should be handled without errors
        """
        entries = {
            (): "empty_path",  # Empty path - should be ignored
            ("Motor",): "single_element",  # Single element path - creates direct component value
            ("Motor", "Product", "Manufacturer"): "T-Motor",  # Valid nested path
        }

        result = empty_model.extract_component_data_from_entries("Motor", entries)

        # Single element paths create direct key-value pairs at component level
        # Empty paths are ignored due to len(path) >= 1 check
        assert result == {"Motor": "single_element", "Product": {"Manufacturer": "T-Motor"}}

    def test_system_uses_last_value_for_duplicate_paths(self, empty_model) -> None:
        """
        System extraction with duplicate paths (last value wins).

        GIVEN: Entry paths with duplicates
        WHEN: The system extracts component data
        THEN: The last value for duplicate paths should be used
        """
        # Create entries with duplicate path by using dict construction
        entries_dict = {}
        entries_dict[("Motor", "Product", "Manufacturer")] = "T-Motor"
        entries_dict[("Motor", "Product", "Manufacturer")] = "AXI"  # Duplicate path, should overwrite
        entries_dict[("Motor", "Product", "Model")] = "F80"

        result = empty_model.extract_component_data_from_entries("Motor", entries_dict)

        assert result["Product"]["Manufacturer"] == "AXI"  # Last value wins
        assert result["Product"]["Model"] == "F80"

    def test_system_preserves_special_characters_in_values(self, empty_model) -> None:
        """
        System extraction with special characters in values.

        GIVEN: Entry values with special characters
        WHEN: The system extracts component data
        THEN: Special characters should be preserved
        """
        entries = {
            ("Component", "Product", "Model"): "Model-X™ (v2.1)",
            ("Component", "Notes"): "Special chars: @#$%^&*()[]{}",
            ("Component", "Version"): "1.0-beta_rc1",
        }

        result = empty_model.extract_component_data_from_entries("Component", entries)

        assert result["Product"]["Model"] == "Model-X™ (v2.1)"
        assert result["Notes"] == "Special chars: @#$%^&*()[]{}"
        assert result["Version"] == "1.0-beta_rc1"

    # Component update robustness tests
    def test_system_handles_circular_references_gracefully(self, empty_model) -> None:
        """
        System updating component with self-referential data structure.

        GIVEN: Component data with circular references
        WHEN: The user updates a component
        THEN: The system should handle it without crashing
        """
        component_data: dict = {"self_ref": None}
        component_data["self_ref"] = component_data  # Create circular reference

        # This should not crash - the model should handle it gracefully
        empty_model.update_component("Circular", component_data)
        assert "Circular" in empty_model.get_component_data()["Components"]

    def test_user_can_add_deeply_nested_component_data(self, empty_model) -> None:
        """
        User updating component with very deeply nested data.

        GIVEN: Very deeply nested component data (20 levels)
        WHEN: The user adds the component
        THEN: All nesting levels should be preserved
        """
        # Create 20 levels of nesting
        deep_data = {}
        current_level = deep_data
        for i in range(20):
            current_level[f"level_{i}"] = {}
            current_level = current_level[f"level_{i}"]
        current_level["final_value"] = "deep_nested_data"

        empty_model.update_component("Deep Component", deep_data)

        stored_data = empty_model.get_component_data()["Components"]["Deep Component"]
        # Navigate to the deepest level
        current = stored_data
        for i in range(20):
            current = current[f"level_{i}"]
        assert current["final_value"] == "deep_nested_data"

    def test_user_can_use_unicode_in_component_data(self, empty_model) -> None:
        """
        User updating component with unicode keys and values.

        GIVEN: Component data with Unicode characters
        WHEN: The user adds the component
        THEN: Unicode should be preserved in keys and values
        """
        component_data = {
            "产品": {"制造商": "大疆", "型号": "Mavic Air 2"},
            "Spécifications": {"Puissance": 100, "Poids": "570g"},
            "Примечания": "Высокопроизводительный дрон",
        }

        empty_model.update_component("Unicode Component", component_data)

        stored_data = empty_model.get_component_data()["Components"]["Unicode Component"]
        assert stored_data["产品"]["制造商"] == "大疆"
        assert stored_data["Spécifications"]["Puissance"] == 100
        assert stored_data["Примечания"] == "Высокопроизводительный дрон"

    # Template derivation edge cases
    def test_system_handles_none_manufacturer_in_template_name(self) -> None:
        """
        System deriving template name with None manufacturer.

        GIVEN: Product data with None manufacturer
        WHEN: The system derives template name
        THEN: The manufacturer should be skipped in the template name
        """
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = ComponentDataModelTemplates({}, component_datatypes, schema)

        component_data = {"Product": {"Manufacturer": None, "Model": "Test Model"}}

        result = model.derive_initial_template_name(component_data)
        assert result == " Test Model"

    def test_system_handles_none_model_in_template_name(self) -> None:
        """
        System deriving template name with None model.

        GIVEN: Product data with None model
        WHEN: The system derives template name
        THEN: The model should be skipped in the template name
        """
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = ComponentDataModelTemplates({}, component_datatypes, schema)

        component_data = {"Product": {"Manufacturer": "Test Corp", "Model": None}}

        result = model.derive_initial_template_name(component_data)
        assert result == "Test Corp "

    def test_system_converts_numeric_values_in_template_name(self) -> None:
        """
        System deriving template name with numeric manufacturer/model values.

        GIVEN: Product data with numeric manufacturer and model
        WHEN: The system derives template name
        THEN: Numbers should be converted to strings
        """
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = ComponentDataModelTemplates({}, component_datatypes, schema)

        component_data = {"Product": {"Manufacturer": 123, "Model": 456}}

        result = model.derive_initial_template_name(component_data)
        assert result == "123 456"

    def test_system_handles_whitespace_in_template_name(self) -> None:
        """
        System deriving template name with whitespace-only values.

        GIVEN: Product data with whitespace in manufacturer and model
        WHEN: The system derives template name
        THEN: Whitespace should be preserved or normalized
        """
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = ComponentDataModelTemplates({}, component_datatypes, schema)

        component_data = {"Product": {"Manufacturer": "   ", "Model": "\t\n"}}

        result = model.derive_initial_template_name(component_data)
        assert result == "    \t\n"

    # Memory efficiency and performance tests
    def test_system_handles_large_number_of_entries(self, empty_model) -> None:
        """
        System extracting component data from a large number of entries.

        GIVEN: A large number of component entries (100+)
        WHEN: The system extracts component data
        THEN: All entries should be processed efficiently
        """
        # Create 1000 entries for a single component
        entries = {}
        for i in range(1000):
            entries[("TestComponent", "Data", f"Field_{i}")] = f"Value_{i}"

        result = empty_model.extract_component_data_from_entries("TestComponent", entries)

        assert len(result["Data"]) == 1000
        assert result["Data"]["Field_0"] == "Value_0"
        assert result["Data"]["Field_999"] == "Value_999"

    def test_system_extracts_data_from_many_components(self, empty_model) -> None:
        """
        System extracting from entries containing many different components.

        GIVEN: Entries containing many different components
        WHEN: The system extracts data for one component
        THEN: Only the specified component data should be extracted
        """
        # Create entries for 100 different components
        entries = {}
        for i in range(100):
            entries[(f"Component_{i}", "Data", "Value")] = f"Data_{i}"

        # Extract data for one specific component
        result = empty_model.extract_component_data_from_entries("Component_50", entries)

        assert result == {"Data": {"Value": "Data_50"}}

    def test_system_handles_concurrent_template_operations(self, empty_model) -> None:
        """
        System multiple template operations in sequence for data consistency.

        GIVEN: A component model
        WHEN: Multiple template operations are performed
        THEN: All operations should complete without conflicts
        """
        # Simulate concurrent-like operations
        for i in range(50):
            empty_model.update_component(f"Component_{i}", {"id": i, "data": f"value_{i}"})

            # Verify intermediate state
            assert empty_model.get_component_data()["Components"][f"Component_{i}"]["id"] == i

        # Verify final state
        assert len(empty_model.get_component_data()["Components"]) >= 50  # At least 50 new components

    # Data integrity validation tests
    def test_system_maintains_data_consistency_after_extraction(self, basic_model) -> None:
        """
        System data consistency after multiple extract operations.

        GIVEN: A component model with existing data
        WHEN: Multiple extract operations are performed
        THEN: Data should remain consistent
        """
        original_data = basic_model.get_component_data().copy()

        # Perform multiple extract operations
        entries = {
            ("NewComponent", "Product", "Manufacturer"): "Test",
            ("NewComponent", "Product", "Model"): "Model",
        }

        for _ in range(10):
            result = basic_model.extract_component_data_from_entries("NewComponent", entries)
            assert result["Product"]["Manufacturer"] == "Test"

        # Original data should be unchanged
        assert basic_model.get_component_data() == original_data

    def test_system_generates_consistent_template_names(self, empty_model) -> None:
        """
        System template name derivation consistency.

        GIVEN: Same product data
        WHEN: Template name is derived multiple times
        THEN: The same name should be generated each time
        """
        component_data = {"Product": {"Manufacturer": "TestCorp", "Model": "ModelX"}}

        # Multiple calls should return the same result
        for _ in range(10):
            result = empty_model.derive_initial_template_name(component_data)
            assert result == "TestCorp ModelX"

    def test_user_can_update_component_idempotently(self, empty_model) -> None:
        """
        User that updating a component with the same data is idempotent.

        GIVEN: A component in the model
        WHEN: The user updates it with the same data multiple times
        THEN: Only one update should be stored
        """
        component_data = {"Type": "Motor", "Specifications": {"Power": 100}}

        # Update component multiple times with same data
        for _ in range(5):
            empty_model.update_component("Motor", component_data)

        # Should have only one component with the correct data
        assert "Motor" in empty_model.get_component_data()["Components"]
        assert empty_model.get_component_data()["Components"]["Motor"] == component_data

    # Error handling and boundary tests
    def test_system_handles_malformed_entry_paths(self, empty_model) -> None:
        """
        System extraction with malformed entry structures.

        GIVEN: Malformed component entry paths
        WHEN: The system extracts component data
        THEN: Malformed paths should be handled gracefully
        """
        entries = {
            ("Motor", "Valid", "Path"): "valid_value",
            ("Motor",): "incomplete_path",
        }

        # Should process valid entries without crashing
        result = empty_model.extract_component_data_from_entries("Motor", entries)
        assert "Valid" in result
        assert result["Valid"]["Path"] == "valid_value"
        assert result["Motor"] == "incomplete_path"

    def test_system_converts_complex_types_in_template_name(self) -> None:
        """
        System deriving template name when manufacturer/model are complex types.

        GIVEN: Product data with complex types (lists, dicts)
        WHEN: The system derives template name
        THEN: Complex types should be converted to strings
        """
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = ComponentDataModelTemplates({}, component_datatypes, schema)

        component_data = {
            "Product": {
                "Manufacturer": ["List", "Manufacturer"],  # List instead of string
                "Model": {"dict": "model"},  # Dict instead of string
            }
        }

        # Should handle gracefully (convert to string)
        result = model.derive_initial_template_name(component_data)
        assert isinstance(result, str)
        assert "List" in result  # Should contain string representation of list
        assert "dict" in result  # Should contain string representation of dict

    def test_user_can_add_component_with_nested_none_values(self, empty_model) -> None:
        """
        User updating component with nested None values.

        GIVEN: Component data with None values at various nesting levels
        WHEN: The user adds the component
        THEN: None values should be preserved at all levels
        """
        component_data = {
            "Product": {"Manufacturer": "TestCorp", "Model": None},
            "Specifications": None,
            "Notes": "Valid note",
        }

        empty_model.update_component("Test Component", component_data)

        stored_data = empty_model.get_component_data()["Components"]["Test Component"]
        assert stored_data["Product"]["Manufacturer"] == "TestCorp"
        assert stored_data["Product"]["Model"] is None
        assert stored_data["Specifications"] is None
        assert stored_data["Notes"] == "Valid note"

    # Integration tests with extract_component_data_from_entries
    def test_user_can_extract_and_update_components(self, empty_model) -> None:
        """
        User complete workflow: extract data, derive template, and update component.

        GIVEN: An empty component model and entries
        WHEN: The user extracts data and then updates it
        THEN: The workflow should complete successfully
        """
        # Step 1: Extract component data from entries
        entries = {
            ("DroneMotor", "Product", "Manufacturer"): "T-Motor",
            ("DroneMotor", "Product", "Model"): "F80 Pro",
            ("DroneMotor", "Specifications", "KV"): "2400",
            ("DroneMotor", "Specifications", "Power"): "500",
        }

        extracted_data = empty_model.extract_component_data_from_entries("DroneMotor", entries)

        # Step 2: Derive template name from extracted data
        template_name = empty_model.derive_initial_template_name(extracted_data)

        # Step 3: Set configuration template
        empty_model.set_configuration_template(template_name)

        # Step 4: Update component with extracted data
        empty_model.update_component("DroneMotor", extracted_data)

        # Verify final state
        assert empty_model.get_component_data()["Configuration template"] == "T-Motor F80 Pro"
        assert empty_model.get_component_data()["Components"]["DroneMotor"]["Product"]["Manufacturer"] == "T-Motor"
        assert empty_model.get_component_data()["Components"]["DroneMotor"]["Specifications"]["KV"] == 2400

    def test_user_can_extract_modify_and_store_component_data(self, empty_model) -> None:
        """
        User workflow where extracted data is modified before component update.

        GIVEN: Component entries
        WHEN: The user extracts, modifies, and stores the data
        THEN: All changes should be preserved
        """
        entries = {
            ("GPS", "Product", "Manufacturer"): "uBlox",
            ("GPS", "Product", "Model"): "NEO-8M",
            ("GPS", "Specifications", "Accuracy"): "2.5",
        }

        # Extract data
        extracted_data = empty_model.extract_component_data_from_entries("GPS", entries)

        # Modify extracted data
        extracted_data["Product"]["Version"] = "1.0"
        extracted_data["Specifications"]["Accuracy"] = 3.0  # Change accuracy
        extracted_data["Notes"] = "Modified component"

        # Update component
        empty_model.update_component("GPS", extracted_data)

        # Verify modifications were preserved
        stored_data = empty_model.get_component_data()["Components"]["GPS"]
        assert stored_data["Product"]["Version"] == "1.0"
        assert stored_data["Specifications"]["Accuracy"] == 3.0
        assert stored_data["Notes"] == "Modified component"

    # Version and compatibility tests
    def test_system_handles_version_field_in_entries(self, empty_model) -> None:
        """
        System extraction properly handles Version fields as strings.

        GIVEN: Entries with version fields
        WHEN: The system extracts component data
        THEN: Version fields should be handled correctly
        """
        entries = {
            ("FC", "Product", "Version"): "1.2.3-beta",
            ("FC", "Firmware", "Version"): "4.1.0",
            ("FC", "Hardware", "Version"): "2.0",
        }

        result = empty_model.extract_component_data_from_entries("FC", entries)

        # Version fields should remain as strings
        assert result["Product"]["Version"] == "1.2.3-beta"
        assert result["Firmware"]["Version"] == "4.1.0"
        assert result["Hardware"]["Version"] == "2.0"

    def test_system_converts_mixed_numeric_strings(self, empty_model) -> None:
        """
        System extraction with mixed numeric and string values.

        GIVEN: Entries with numeric strings and actual numbers
        WHEN: The system extracts component data
        THEN: Values should be converted appropriately
        """
        entries = {
            ("Sensor", "ID"): "12345",  # Should be converted to int
            ("Sensor", "SerialNumber"): "SN-ABC123",  # Should remain string
            ("Sensor", "CalibrationValue"): "3.14159",  # Should be converted to float
            ("Sensor", "Notes"): "Calibrated on 2024-01-01",  # Should remain string
        }

        result = empty_model.extract_component_data_from_entries("Sensor", entries)

        assert result["ID"] == 12345  # int
        assert result["SerialNumber"] == "SN-ABC123"  # string
        assert result["CalibrationValue"] == 3.14159  # float
        assert result["Notes"] == "Calibrated on 2024-01-01"  # string
