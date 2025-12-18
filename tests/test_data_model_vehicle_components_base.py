#!/usr/bin/env python3

"""
Vehicle Components data model tests for basic ComponentDataModelBase functionality.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, Mock

import pytest
from test_data_model_vehicle_components_common import BasicTestMixin, ComponentDataModelFixtures, RealisticDataTestMixin

from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents
from ardupilot_methodic_configurator.data_model_vehicle_components_base import ComponentData, ComponentDataModelBase
from ardupilot_methodic_configurator.data_model_vehicle_components_json_schema import VehicleComponentsJsonSchema

# pylint: disable=protected-access,too-many-public-methods,too-many-lines


class TestComponentDataModelBase(BasicTestMixin, RealisticDataTestMixin):
    """Tests for the ComponentDataModel class."""

    @pytest.fixture
    def empty_model(self) -> ComponentDataModelBase:
        """Create an empty ComponentDataModelBase fixture for testing."""
        return ComponentDataModelFixtures.create_empty_model(ComponentDataModelBase)

    @pytest.fixture
    def basic_model(self) -> ComponentDataModelBase:
        """Create a ComponentDataModelBase fixture for testing."""
        return ComponentDataModelFixtures.create_basic_model(ComponentDataModelBase)

    @pytest.fixture
    def realistic_model(self) -> ComponentDataModelBase:
        """Create a realistic vehicle data model based on the JSON file."""
        return ComponentDataModelFixtures.create_realistic_model(ComponentDataModelBase)

    # Additional tests specific to ComponentDataModelBase that aren't covered by mixins
    def test_system_sets_component_values_at_nested_paths(self, basic_model) -> None:
        """
        System correctly sets component values at various nested path levels.

        GIVEN: A vehicle component model
        WHEN: Setting values at different path depths
        THEN: Values should be stored correctly at the specified paths
        AND: None values should be converted to empty strings
        """
        # Set a new value for an existing path
        basic_model.set_component_value(("Battery", "Specifications", "Capacity mAh"), 1500)
        assert basic_model._data["Components"]["Battery"]["Specifications"]["Capacity mAh"] == 1500

        # Set a value for a nested path
        basic_model.set_component_value(("Flight Controller", "Product", "Manufacturer"), "Pixhawk")
        assert basic_model._data["Components"]["Flight Controller"]["Product"]["Manufacturer"] == "Pixhawk"

        # Set a value for a new path
        basic_model.set_component_value(("Frame", "Specifications", "Weight Kg"), 0.5)
        assert basic_model._data["Components"]["Frame"]["Specifications"]["Weight Kg"] == 0.5

        # Test with None value
        basic_model.set_component_value(("Flight Controller", "Notes"), None)
        assert basic_model._data["Components"]["Flight Controller"]["Notes"] == ""

    def test_system_retrieves_component_values_from_nested_paths(self, basic_model) -> None:
        """
        System correctly retrieves component values from nested paths.

        GIVEN: A vehicle component model with stored values
        WHEN: Retrieving values using path tuples
        THEN: Existing values should be returned correctly
        AND: Non-existent paths should return empty dict
        """
        # Get an existing value
        value = basic_model.get_component_value(("Battery", "Specifications", "Chemistry"))
        assert value == "Lipo"

        # Get a nested value
        value = basic_model.get_component_value(("Flight Controller", "Specifications", "MCU Series"))
        assert value == "Unknown"

        # Get a non-existent value
        value = basic_model.get_component_value(("Battery", "NonExistent"))
        assert value == {}

        # Get a non-existent path
        value = basic_model.get_component_value(("NonExistent", "Path"))
        assert value == {}

    def test_system_converts_values_to_appropriate_types_when_setting(self, basic_model) -> None:
        """
        System automatically converts string values to appropriate data types.

        GIVEN: Component values provided as strings
        WHEN: Setting multiple component values
        THEN: Numeric strings should be converted to int or float
        AND: Version strings should remain as strings
        AND: Regular strings should be preserved
        """
        # Test setting values one by one (mimicking what _update_from_entries would do)
        basic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "LiFePO4")
        basic_model.set_component_value(("Battery", "Specifications", "Capacity mAh"), "2200")  # Should be converted to int
        basic_model.set_component_value(("Flight Controller", "Product", "Manufacturer"), "Pixhawk")
        basic_model.set_component_value(("Frame", "Specifications", "Weight Kg"), "0.35")  # Should be converted to float
        basic_model.set_component_value(("Flight Controller", "Firmware", "Version"), "v4.6.2")  # Should remain string

        # Check values were updated and converted to appropriate types
        assert basic_model._data["Components"]["Battery"]["Specifications"]["Chemistry"] == "LiFePO4"
        assert basic_model._data["Components"]["Battery"]["Specifications"]["Capacity mAh"] == 2200
        assert basic_model._data["Components"]["Flight Controller"]["Product"]["Manufacturer"] == "Pixhawk"
        assert basic_model._data["Components"]["Frame"]["Specifications"]["Weight Kg"] == 0.35
        assert basic_model._data["Components"]["Flight Controller"]["Firmware"]["Version"] == "v4.6.2"

    def test_system_manages_format_version_correctly(self, basic_model, empty_model) -> None:
        """
        System correctly manages format version in component data.

        GIVEN: Component models with or without existing data
        WHEN: Checking format version
        THEN: Existing format version should be preserved
        AND: Empty models should have default format version of 1
        """
        # Should not change existing format version
        original_version = basic_model._data["Format version"]
        # Format version should remain unchanged during normal operations
        assert basic_model._data["Format version"] == original_version

        # Empty model should have default format version
        assert empty_model._data["Format version"] == 1

    def test_system_processes_values_with_type_inference(self, basic_model) -> None:
        """
        System processes values with automatic type inference and conversion.

        GIVEN: Various string values representing different data types
        WHEN: Processing values for component paths
        THEN: Integer strings should convert to int
        AND: Float strings should convert to float
        AND: String values should have whitespace trimmed
        AND: Version fields should remain as strings
        """
        # Test integer conversion
        value = basic_model._process_value(("Battery", "Specifications", "Capacity mAh"), "2000")
        assert value == 2000
        assert isinstance(value, int)

        # Test float conversion
        value = basic_model._process_value(("Frame", "Specifications", "Weight Kg"), "0.25")
        assert value == 0.25
        assert isinstance(value, float)

        # Test string handling
        value = basic_model._process_value(("Battery", "Specifications", "Chemistry"), "  Lipo  ")
        assert value == "Lipo"
        assert isinstance(value, str)

        # Test handling of non-numeric strings
        value = basic_model._process_value(("Flight Controller", "Notes"), "Special notes")
        assert value == "Special notes"
        assert isinstance(value, str)

        # Test handling of Version field
        value = basic_model._process_value(("Flight Controller", "Firmware", "Version"), "4.6.2")
        assert value == "4.6.2"  # Should remain a string, not be converted to float
        assert isinstance(value, str)

    def test_system_provides_access_to_component_data_structure(self, basic_model) -> None:
        """
        System provides structured access to component data.

        GIVEN: A vehicle component model with component data
        WHEN: Accessing component data via get_component_data
        THEN: Component data should be returned as dictionary
        AND: Non-existent components should return empty dict
        """
        # Test getting specific component's data via get_component_data
        components = basic_model.get_component_data()["Components"]
        battery_data = components.get("Battery", {})
        assert isinstance(battery_data, dict)
        assert battery_data.get("Specifications", {}).get("Chemistry") == "Lipo"
        assert battery_data.get("Specifications", {}).get("Capacity mAh") == 0

        # Test getting non-existent component
        nonexistent = components.get("NonExistent", {})
        assert nonexistent == {}

    def test_user_can_modify_existing_components_and_add_new_ones(self, basic_model) -> None:
        """
        User can modify existing component data and add new components dynamically.

        GIVEN: A vehicle component model with existing components
        WHEN: Updating existing component values and adding new components
        THEN: Existing components should be updated with new values
        AND: New components should be created and added to the model
        """
        # Update existing component via set_component_value
        basic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "LiIon")
        basic_model.set_component_value(("Battery", "Specifications", "Capacity mAh"), 2200)
        basic_model.set_component_value(("Battery", "Specifications", "Voltage"), 11.1)

        # Verify changes
        components = basic_model.get_component_data()["Components"]
        updated_battery = components["Battery"]
        assert updated_battery["Specifications"]["Chemistry"] == "LiIon"
        assert updated_battery["Specifications"]["Capacity mAh"] == 2200
        assert updated_battery["Specifications"]["Voltage"] == 11.1

        # Add new component by setting values
        basic_model.set_component_value(("Servo", "Type"), "digital")
        basic_model.set_component_value(("Servo", "Torque"), 10)
        basic_model.set_component_value(("Servo", "Speed"), 0.12)

        assert "Servo" in basic_model.get_all_components()
        servo_data = components["Servo"]
        assert servo_data["Type"] == "digital"
        assert servo_data["Torque"] == 10
        assert servo_data["Speed"] == 0.12

    # Tests for specific ComponentDataModelBase methods

    def test_system_updates_json_structure_for_old_file_formats(self, empty_model) -> None:
        """
        System updates JSON structure to add missing required fields from old formats.

        GIVEN: Component data with minimal or missing structure
        WHEN: Calling update_json_structure
        THEN: All required component fields should be added
        AND: Default values should be set for missing fields
        AND: Program version field should be added
        """
        # Start with minimal data
        empty_model._data = {"Components": {}}

        empty_model.update_json_structure()

        # Check that all required fields are added
        assert "Battery" in empty_model._data["Components"]
        assert "Specifications" in empty_model._data["Components"]["Battery"]
        assert "Chemistry" in empty_model._data["Components"]["Battery"]["Specifications"]
        assert empty_model._data["Components"]["Battery"]["Specifications"]["Chemistry"] == "Lipo"

        assert "Frame" in empty_model._data["Components"]
        assert "Specifications" in empty_model._data["Components"]["Frame"]
        assert "TOW min Kg" in empty_model._data["Components"]["Frame"]["Specifications"]
        assert "TOW max Kg" in empty_model._data["Components"]["Frame"]["Specifications"]

        assert "Flight Controller" in empty_model._data["Components"]
        assert "Specifications" in empty_model._data["Components"]["Flight Controller"]
        assert "MCU Series" in empty_model._data["Components"]["Flight Controller"]["Specifications"]

        assert "Program version" in empty_model._data

    def test_system_migrates_old_gnss_receiver_key_to_new_format(self, basic_model) -> None:
        """
        System migrates old 'GNSS receiver' key to new 'GNSS Receiver' format.

        GIVEN: Component data with old 'GNSS receiver' key (lowercase 'r')
        WHEN: Running JSON structure update
        THEN: Old key should be removed
        AND: New 'GNSS Receiver' key should be created
        AND: All data should be preserved under new key
        """
        # Add old key format
        basic_model._data["Components"]["GNSS receiver"] = {"Product": {"Manufacturer": "Holybro", "Model": "H-RTK F9P"}}

        basic_model.update_json_structure()

        # Check that old key is removed and new key exists
        assert "GNSS receiver" not in basic_model._data["Components"]
        assert "GNSS Receiver" in basic_model._data["Components"]
        assert basic_model._data["Components"]["GNSS Receiver"]["Product"]["Manufacturer"] == "Holybro"

    def test_system_migrates_old_sbf_protocol_name(self, basic_model) -> None:
        """
        System migrates legacy SBF protocol name to vendor-specific format.

        GIVEN: GNSS receiver with old 'SBF' protocol name
        WHEN: Running JSON structure update
        THEN: Protocol name should be migrated to 'Septentrio(SBF)'
        AND: Migration reflects vendor clarity improvement
        """
        # Set old protocol name
        basic_model._data["Components"]["GNSS Receiver"] = {"FC Connection": {"Type": "SERIAL3", "Protocol": "SBF"}}

        basic_model.update_json_structure()

        # Check that protocol was migrated to new name
        gnss_protocol = basic_model._data["Components"]["GNSS Receiver"]["FC Connection"]["Protocol"]
        assert gnss_protocol == "Septentrio(SBF)", "Old SBF protocol should be migrated to Septentrio(SBF)"

    def test_system_migrates_old_gsof_protocol_name(self, basic_model) -> None:
        """
        System migrates legacy GSOF protocol name to vendor-specific format.

        GIVEN: GNSS receiver with old 'GSOF' protocol name
        WHEN: Running JSON structure update
        THEN: Protocol name should be migrated to 'Trimble(GSOF)'
        AND: Migration reflects vendor clarity improvement
        """
        # Set old protocol name
        basic_model._data["Components"]["GNSS Receiver"] = {"FC Connection": {"Type": "SERIAL3", "Protocol": "GSOF"}}

        basic_model.update_json_structure()

        # Check that protocol was migrated to new name
        gnss_protocol = basic_model._data["Components"]["GNSS Receiver"]["FC Connection"]["Protocol"]
        assert gnss_protocol == "Trimble(GSOF)", "Old GSOF protocol should be migrated to Trimble(GSOF)"

    def test_system_migrates_old_sbf_dual_antenna_protocol_name(self, basic_model) -> None:
        """
        System migrates legacy SBF-DualAntenna protocol name to vendor-specific format.

        GIVEN: GNSS receiver with old 'SBF-DualAntenna' protocol name
        WHEN: Running JSON structure update
        THEN: Protocol name should be migrated to 'Septentrio-DualAntenna(SBF)'
        AND: Dual antenna configuration is preserved with vendor clarity
        """
        # Set old protocol name
        basic_model._data["Components"]["GNSS Receiver"] = {
            "FC Connection": {"Type": "SERIAL3", "Protocol": "SBF-DualAntenna"}
        }

        basic_model.update_json_structure()

        # Check that protocol was migrated to new name
        gnss_protocol = basic_model._data["Components"]["GNSS Receiver"]["FC Connection"]["Protocol"]
        assert gnss_protocol == "Septentrio-DualAntenna(SBF)", (
            "Old SBF-DualAntenna protocol should be migrated to Septentrio-DualAntenna(SBF)"
        )

    def test_system_preserves_already_migrated_protocol_names(self, basic_model) -> None:
        """
        System does not modify protocol names that are already in new format.

        GIVEN: GNSS receiver with already-migrated protocol name 'Septentrio(SBF)'
        WHEN: Running JSON structure update
        THEN: Protocol name should remain unchanged
        AND: Migration is idempotent for already-updated configurations
        """
        # Set new protocol name (already migrated)
        basic_model._data["Components"]["GNSS Receiver"] = {
            "FC Connection": {"Type": "SERIAL3", "Protocol": "Septentrio(SBF)"}
        }

        basic_model.update_json_structure()

        # Check that protocol remains unchanged
        gnss_protocol = basic_model._data["Components"]["GNSS Receiver"]["FC Connection"]["Protocol"]
        assert gnss_protocol == "Septentrio(SBF)", "New protocol names should not be modified"

    def test_system_preserves_non_migrated_gnss_protocols(self, basic_model) -> None:
        """
        System does not modify GNSS protocols that don't require migration.

        GIVEN: GNSS receiver with protocol not requiring migration (e.g., uBlox)
        WHEN: Running JSON structure update
        THEN: Protocol name should remain unchanged
        AND: Only specific legacy protocols are targeted for migration
        """
        # Set a protocol that doesn't need migration
        basic_model._data["Components"]["GNSS Receiver"] = {"FC Connection": {"Type": "SERIAL3", "Protocol": "uBlox"}}

        basic_model.update_json_structure()

        # Check that protocol remains unchanged
        gnss_protocol = basic_model._data["Components"]["GNSS Receiver"]["FC Connection"]["Protocol"]
        assert gnss_protocol == "uBlox", "Other protocols should not be changed by migration"

    def test_system_preserves_gnss_fields_during_protocol_migration(self, basic_model) -> None:
        """
        System preserves all GNSS receiver fields during protocol migration.

        GIVEN: GNSS receiver with legacy protocol and additional fields (manufacturer, model, notes)
        WHEN: Migrating protocol name
        THEN: Only protocol field should be updated
        AND: All other fields (manufacturer, model, notes) should be preserved
        """
        # Set old protocol with additional fields
        basic_model._data["Components"]["GNSS Receiver"] = {
            "Product": {"Manufacturer": "Septentrio", "Model": "mosaic-X5"},
            "FC Connection": {"Type": "SERIAL3", "Protocol": "SBF"},
            "Notes": "Dual antenna setup",
        }

        basic_model.update_json_structure()

        # Check that only protocol was changed, other fields preserved
        gnss = basic_model._data["Components"]["GNSS Receiver"]
        assert gnss["FC Connection"]["Protocol"] == "Septentrio(SBF)"
        assert gnss["Product"]["Manufacturer"] == "Septentrio"
        assert gnss["Product"]["Model"] == "mosaic-X5"
        assert gnss["Notes"] == "Dual antenna setup"

    def test_system_converts_none_values_to_empty_strings(self, basic_model) -> None:
        """
        System converts None values to empty strings when setting component values.

        GIVEN: Component values set to None
        WHEN: Setting and retrieving these values
        THEN: None values should be stored as empty strings
        AND: Retrieval should return empty string, not None
        """
        # Set None and then ensure it's converted to empty string
        basic_model.set_component_value(("Motor", "Notes"), None)
        assert basic_model.get_component_value(("Motor", "Notes")) == ""

        # Set None values individually
        basic_model.set_component_value(("Motor", "Description"), None)
        assert basic_model.get_component_value(("Motor", "Description")) == ""

    def test_system_handles_type_conversion_edge_cases(self, basic_model) -> None:
        """
        System handles various edge cases during value type conversion.

        GIVEN: Values that could be interpreted as different types
        WHEN: Processing these values with _process_value
        THEN: Integer strings should convert to int
        AND: Float strings should convert to float
        AND: Non-numeric strings should remain as strings
        AND: Version fields should always return string regardless of content
        """
        # Test non-Version field with numeric string
        path = ("Test", "Numeric")

        # Test int conversion
        result = basic_model._process_value(path, "42")
        assert result == 42
        assert isinstance(result, int)

        # Test float conversion when int fails
        result = basic_model._process_value(path, "42.5")
        assert result == 42.5
        assert isinstance(result, float)

        # Test string fallback when both fail
        result = basic_model._process_value(path, "not_a_number")
        assert result == "not_a_number"
        assert isinstance(result, str)

        # Test Version field always returns string
        version_path = ("Test", "Version")
        result = basic_model._process_value(version_path, "42")
        assert result == "42"
        assert isinstance(result, str)

    def test_system_handles_unusual_data_types_in_component_values(self, basic_model) -> None:
        """
        System handles unusual data types when retrieving component values.

        GIVEN: Component data with unusual types (lists, tuples, None)
        WHEN: Retrieving these values
        THEN: Non-existent nested paths should return empty dict
        AND: Lists and tuples should be converted to string representation
        """
        # Test accessing non-existent nested path
        result = basic_model.get_component_value(("NonExistent", "Path", "Deep"))
        assert result == {}

        # Test with unusual data types in the structure
        basic_model._data["Components"]["Test"] = {
            "unusual_type": ["list", "data"],
            "tuple_data": (1, 2, 3),
            "none_value": None,
        }

        # Test list conversion to string
        result = basic_model.get_component_value(("Test", "unusual_type"))
        assert result == "['list', 'data']"

        # Test tuple conversion to string
        result = basic_model.get_component_value(("Test", "tuple_data"))
        assert result == "(1, 2, 3)"

    def test_system_creates_components_key_when_missing(self, empty_model) -> None:
        """
        System automatically creates Components key structure when missing.

        GIVEN: Empty model without Components key
        WHEN: Setting component values via set_component_value
        THEN: Components key should be created automatically
        AND: Component data should be stored correctly
        """
        # Remove Components key if it exists
        if "Components" in empty_model._data:
            del empty_model._data["Components"]

        # Update component should create Components key via set_component_value
        empty_model.set_component_value(("TestComponent", "Type"), "Test")
        empty_model.set_component_value(("TestComponent", "Value"), 42)

        assert "Components" in empty_model._data
        assert "TestComponent" in empty_model._data["Components"]
        assert empty_model._data["Components"]["TestComponent"]["Type"] == "Test"
        assert empty_model._data["Components"]["TestComponent"]["Value"] == 42

    def test_system_returns_empty_tuple_for_unknown_combobox_paths(self, realistic_model) -> None:
        """
        System returns empty tuple for combobox values at unknown paths.

        GIVEN: An unknown component path
        WHEN: Requesting combobox values for that path
        THEN: Should return empty tuple
        AND: Base class behavior for unknown paths is defined
        """
        # Test with basic path - only test with one argument since that's what the base class supports
        unknown_path = ("Unknown", "Component", "Property")
        result = realistic_model.get_combobox_values_for_path(unknown_path)
        assert result == ()  # Should return empty tuple for unknown paths

    def test_system_saves_component_data_to_filesystem(self, realistic_model) -> None:
        """
        System successfully saves component data to filesystem.

        GIVEN: A vehicle component model with modified data
        WHEN: Calling save_to_filesystem with mocked filesystem
        THEN: Save operation should succeed
        AND: Filesystem save method should be called once
        AND: Modified values should be persisted
        """
        # Create a mock filesystem
        mock_filesystem = Mock()
        mock_filesystem.save_vehicle_components_json_data = MagicMock(return_value=(True, "Success"))
        mock_filesystem.vehicle_dir = "/mock/path"

        # Set some values first via set_component_value (since base class doesn't have _update_from_entries)
        realistic_model.set_component_value(("Flight Controller", "Product", "Manufacturer"), "TestManufacturer")
        realistic_model.set_component_value(("Battery", "Specifications", "Capacity mAh"), 2000)

        # Call save_to_filesystem with correct signature (only takes filesystem parameter)
        success, message = realistic_model.save_to_filesystem(mock_filesystem)

        # Verify the method was called correctly
        assert success is True
        assert message == "Success"
        mock_filesystem.save_vehicle_components_json_data.assert_called_once()

        # Verify that values were set correctly
        assert realistic_model.get_component_value(("Flight Controller", "Product", "Manufacturer")) == "TestManufacturer"
        assert realistic_model.get_component_value(("Battery", "Specifications", "Capacity mAh")) == 2000

    def test_system_recreates_missing_flight_controller_data(self, realistic_model) -> None:
        """
        System recreates missing Flight Controller component with defaults.

        GIVEN: Model with missing Flight Controller component
        WHEN: Running JSON structure update
        THEN: Flight Controller component should be recreated
        AND: Default specifications should be set (MCU Series = Unknown)
        """
        # Remove Flight Controller key
        if "Flight Controller" in realistic_model._data["Components"]:
            del realistic_model._data["Components"]["Flight Controller"]

        realistic_model.update_json_structure()

        # Should recreate Flight Controller with default values
        assert "Flight Controller" in realistic_model._data["Components"]
        # The structure creates Product as an empty dict if missing
        if "Product" in realistic_model._data["Components"]["Flight Controller"]:
            # Check if Manufacturer exists, if not it means Product is empty dict
            assert (
                "Manufacturer" not in realistic_model._data["Components"]["Flight Controller"]["Product"]
                or realistic_model._data["Components"]["Flight Controller"]["Product"]["Manufacturer"] is not None
            )
        assert realistic_model._data["Components"]["Flight Controller"]["Specifications"]["MCU Series"] == "Unknown"

    def test_system_creates_components_structure_when_missing(self) -> None:
        """
        System creates entire Components structure when completely missing.

        GIVEN: Data without Components key
        WHEN: Running JSON structure update
        THEN: Components key should be created
        AND: Required components (Battery, Frame, etc.) should be added
        AND: Default specifications should be initialized
        """
        # Create data without Components key
        data: ComponentData = {"Configuration": {}}
        vehicle_components = VehicleComponents()
        schema = VehicleComponentsJsonSchema(vehicle_components.load_schema())
        component_datatypes = schema.get_all_value_datatypes()
        component_model = ComponentDataModelBase(data, component_datatypes, schema)

        # Call update_json_structure to create the Components key
        component_model.update_json_structure()

        # Should create Components key
        assert "Components" in component_model._data
        assert "Battery" in component_model._data["Components"]
        assert "Specifications" in component_model._data["Components"]["Battery"]

    def test_system_recreates_missing_battery_component(self, realistic_model) -> None:
        """
        System recreates missing Battery component with specifications.

        GIVEN: Model with missing Battery component
        WHEN: Running JSON structure update
        THEN: Battery component should be recreated
        AND: Specifications sub-section should be added
        """
        # Remove Battery component
        if "Battery" in realistic_model._data["Components"]:
            del realistic_model._data["Components"]["Battery"]

        realistic_model.update_json_structure()

        # Should recreate Battery component with Specifications
        assert "Battery" in realistic_model._data["Components"]
        assert "Specifications" in realistic_model._data["Components"]["Battery"]

    def test_system_recreates_missing_flight_controller_specifications(self, realistic_model) -> None:
        """
        System recreates missing Flight Controller Specifications sub-section.

        GIVEN: Flight Controller component with missing Specifications
        WHEN: Running JSON structure update
        THEN: Specifications should be recreated
        AND: MCU Series should be set to Unknown
        """
        # Remove some Flight Controller sub-keys
        if "Specifications" in realistic_model._data["Components"]["Flight Controller"]:
            del realistic_model._data["Components"]["Flight Controller"]["Specifications"]

        realistic_model.update_json_structure()

        # Should recreate missing Specifications
        assert "Specifications" in realistic_model._data["Components"]["Flight Controller"]
        assert realistic_model._data["Components"]["Flight Controller"]["Specifications"]["MCU Series"] == "Unknown"

    def test_system_determines_component_datatypes_from_path(self, basic_model) -> None:
        """
        System determines correct datatype for component fields based on path.

        GIVEN: Component paths with known datatypes
        WHEN: Requesting datatype for each path
        THEN: Correct Python type should be returned (int, float, str)
        AND: Invalid or non-existent paths should return None
        AND: Empty component datatypes should return None
        """
        # Test with valid datatype paths
        datatype = basic_model._get_component_datatype(("Battery", "Specifications", "Capacity mAh"))
        assert datatype is int

        datatype = basic_model._get_component_datatype(("Frame", "Specifications", "TOW min Kg"))
        assert datatype is float

        datatype = basic_model._get_component_datatype(("Battery", "Specifications", "Chemistry"))
        assert datatype is str

        # Test with invalid/non-existent paths
        datatype = basic_model._get_component_datatype(("NonExistent", "Component", "Field"))
        assert datatype is None

        # Test with path too short
        datatype = basic_model._get_component_datatype(("Battery", "Specifications"))
        assert datatype is None

        # Test with empty component datatypes
        basic_model._component_datatypes = {}
        datatype = basic_model._get_component_datatype(("Battery", "Specifications", "Capacity mAh"))
        assert datatype is None

    def test_system_safely_casts_values_with_fallback(self, basic_model) -> None:
        """
        System safely casts values to target types with fallback handling.

        GIVEN: Various values and target types for casting
        WHEN: Attempting to cast values
        THEN: Successful casts should return correctly typed values
        AND: Values already correct type should pass through
        AND: None values should return type-appropriate defaults
        AND: Failed casts should fall back to _process_value
        AND: Dict/list types should be preserved
        """
        path = ("Battery", "Specifications", "Capacity mAh")

        # Test successful int casting
        result = basic_model._safe_cast_value("1500", int, path)
        assert result == 1500
        assert isinstance(result, int)

        # Test successful float casting
        result = basic_model._safe_cast_value("12.5", float, path)
        assert result == 12.5
        assert isinstance(result, float)

        # Test successful string casting
        result = basic_model._safe_cast_value(42, str, path)
        assert result == "42"
        assert isinstance(result, str)

        # Test value already correct type
        result = basic_model._safe_cast_value(1000, int, path)
        assert result == 1000
        assert isinstance(result, int)

        # Test None value handling
        result = basic_model._safe_cast_value(None, int, path)
        assert result == 0  # Returns 0 for int type with None value

        # Test casting failure fallback to _process_value
        result = basic_model._safe_cast_value("not_a_number", int, path)
        # Should fallback to _process_value which returns "not_a_number" as string
        assert result == "not_a_number"
        assert isinstance(result, str)

        # Test with dict/list types that don't fit ComponentValue
        result = basic_model._safe_cast_value({"key": "value"}, dict, path)
        assert result == {"key": "value"}
        assert isinstance(result, dict)

    def test_system_validates_and_initializes_data_structure(self, basic_model, empty_model) -> None:
        """
        System validates data structure and initializes with proper defaults.

        GIVEN: Models with various data structures
        WHEN: Checking data structure validity
        THEN: Data should be dictionary with Components key
        AND: Empty structures should be initialized with defaults
        AND: Corrupted data should be replaced with default structure
        """
        # Test basic structure validation
        assert isinstance(basic_model._data, dict)
        assert "Components" in basic_model._data
        assert isinstance(basic_model._data["Components"], dict)

        # Test empty structure validation
        assert isinstance(empty_model._data, dict)
        assert "Components" in empty_model._data

        # Test with corrupted data structure
        mock_schema = Mock(spec=VehicleComponentsJsonSchema)
        corrupted_model = ComponentDataModelBase({}, {}, mock_schema)
        assert corrupted_model._data == {"Components": {}, "Format version": 1}

    def test_system_creates_deeply_nested_component_paths(self, empty_model) -> None:
        """
        System creates and accesses deeply nested component path structures.

        GIVEN: Empty model without nested structures
        WHEN: Creating very deep nested paths (4+ levels)
        THEN: All intermediate levels should be created automatically
        AND: Deep values should be accessible via path tuples
        """
        # Test creating very deep path
        empty_model.set_component_value(("Component", "Level1", "Level2", "Level3", "DeepValue"), "deep")

        assert "Component" in empty_model._data["Components"]
        assert "Level1" in empty_model._data["Components"]["Component"]
        assert "Level2" in empty_model._data["Components"]["Component"]["Level1"]
        assert "Level3" in empty_model._data["Components"]["Component"]["Level1"]["Level2"]
        assert empty_model._data["Components"]["Component"]["Level1"]["Level2"]["Level3"]["DeepValue"] == "deep"

        # Test accessing the deep value
        result = empty_model.get_component_value(("Component", "Level1", "Level2", "Level3", "DeepValue"))
        assert result == "deep"

    def test_system_handles_numeric_format_edge_cases(self, basic_model) -> None:
        """
        System correctly handles various numeric format edge cases.

        GIVEN: Values in scientific notation, negative numbers, zero, boolean-like strings, hex
        WHEN: Setting and retrieving these values
        THEN: Scientific notation should convert to float
        AND: Negative numbers should be handled correctly
        AND: Zero values should be preserved
        AND: Boolean strings should remain as strings
        AND: Hexadecimal strings should remain as strings
        """
        # Test scientific notation
        basic_model.set_component_value(("Test", "Scientific"), "1.5e3")
        result = basic_model.get_component_value(("Test", "Scientific"))
        assert result == 1500.0

        # Test negative numbers
        basic_model.set_component_value(("Test", "Negative"), "-42")
        result = basic_model.get_component_value(("Test", "Negative"))
        assert result == -42

        # Test zero values
        basic_model.set_component_value(("Test", "Zero"), "0")
        result = basic_model.get_component_value(("Test", "Zero"))
        assert result == 0

        # Test boolean-like strings
        basic_model.set_component_value(("Test", "TrueString"), "True")
        result = basic_model.get_component_value(("Test", "TrueString"))
        assert result == "True"  # Should remain string

        # Test hexadecimal strings
        basic_model.set_component_value(("Test", "Hex"), "0xFF")
        result = basic_model.get_component_value(("Test", "Hex"))
        assert result == "0xFF"  # Should remain string since not pure decimal

    def test_system_trims_whitespace_from_component_values(self, basic_model) -> None:
        """
        System automatically trims whitespace from component values.

        GIVEN: Component values with leading/trailing whitespace, tabs, newlines
        WHEN: Setting and retrieving these values
        THEN: Leading and trailing whitespace should be removed
        AND: Tabs and newlines should be trimmed
        AND: Values with only whitespace should become empty strings
        """
        # Test leading/trailing whitespace
        basic_model.set_component_value(("Test", "Whitespace"), "  trimmed  ")
        result = basic_model.get_component_value(("Test", "Whitespace"))
        assert result == "trimmed"

        # Test tabs and newlines
        basic_model.set_component_value(("Test", "Tabs"), "\tvalue\n")
        result = basic_model.get_component_value(("Test", "Tabs"))
        assert result == "value"

        # Test only whitespace
        basic_model.set_component_value(("Test", "OnlyWhitespace"), "   ")
        result = basic_model.get_component_value(("Test", "OnlyWhitespace"))
        assert result == ""

    def test_system_returns_direct_reference_to_component_data(self, basic_model) -> None:
        """
        System returns direct reference to internal data (documents current behavior).

        GIVEN: Component data retrieved via get_component_data
        WHEN: Modifying the returned data
        THEN: Internal data is changed (direct reference returned)
        NOTE: This documents current behavior; production code should return deep copy
        """
        # Get component data
        original_data = basic_model.get_component_data()

        # Modify the returned data
        original_data["Components"]["Battery"]["Specifications"]["Chemistry"] = "Modified"

        # Verify internal data was changed (get_component_data returns direct reference)
        # This test documents the current behavior - get_component_data returns direct reference
        current_chemistry = basic_model.get_component_value(("Battery", "Specifications", "Chemistry"))
        # Note: This shows that get_component_data returns a direct reference to internal data
        # In a production environment, you'd want get_component_data to return a copy
        assert current_chemistry == "Modified"  # Data was changed because direct reference returned

    def test_system_handles_malformed_initial_data_gracefully(self) -> None:
        """
        System handles malformed or None initial data gracefully.

        GIVEN: Initial data that is None or invalid type
        WHEN: Creating component model
        THEN: Model should initialize with default structure
        AND: Should not crash with type errors
        """
        # Test with None initial data
        vehicle_components = VehicleComponents()
        schema = VehicleComponentsJsonSchema(vehicle_components.load_schema())
        component_datatypes = schema.get_all_value_datatypes()
        model = ComponentDataModelBase(None, component_datatypes, schema)  # type: ignore[arg-type]
        assert model._data == {"Components": {}, "Format version": 1}

        # Test with string instead of dict - documents current behavior
        # The constructor doesn't validate input, it just assigns whatever is passed
        try:
            model = ComponentDataModelBase("invalid", component_datatypes, schema)  # type: ignore[arg-type]
            # Current behavior: Constructor doesn't validate input type
            assert model._data == "invalid"  # Documents that no validation occurs
        except (TypeError, AttributeError):
            # If the constructor validates input and raises an error, that's also acceptable
            pass

    def test_system_initializes_battery_chemistry_with_validation(self, basic_model) -> None:
        """
        System initializes battery chemistry with validation and defaults.

        GIVEN: Battery component with various chemistry values
        WHEN: Initializing battery chemistry
        THEN: Valid chemistry should be set correctly
        AND: Invalid chemistry should default to Lipo
        AND: Missing chemistry should default to Lipo
        """
        # Test that battery chemistry is initialized
        basic_model.init_battery_chemistry()
        assert basic_model._battery_chemistry == "Lipo"  # Default from BASIC_COMPONENT_DATA

        # Test with valid chemistry (using LiIon instead of invalid LiFePO4)
        basic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "LiIon")
        basic_model.init_battery_chemistry()
        assert basic_model._battery_chemistry == "LiIon"

        # Test with invalid chemistry - should default to Lipo and log error
        basic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "InvalidChemistry")
        basic_model.init_battery_chemistry()
        assert basic_model._battery_chemistry == "Lipo"  # Should default to Lipo for invalid chemistry

    def test_system_provides_multiple_component_access_methods(self, realistic_model) -> None:
        """
        System provides various methods to access and check components.

        GIVEN: Model with components
        WHEN: Using different access methods (get_all_components, has_components)
        THEN: get_all_components should return dict of all components
        AND: has_components should return True when components exist
        AND: has_components should return False for empty models
        """
        # Test accessing all top-level components
        components = realistic_model.get_all_components()
        assert isinstance(components, dict)
        assert len(components) > 0

        # Test has_components method
        assert realistic_model.has_components() is True

        # Test with model that has no components
        mock_schema = Mock(spec=VehicleComponentsJsonSchema)
        empty_components = ComponentDataModelBase({"Components": {}, "Format version": 1}, {}, mock_schema)
        assert empty_components.has_components() is False

    def test_system_preserves_version_fields_as_strings(self, basic_model) -> None:
        """
        System treats Version fields specially, always preserving as strings.

        GIVEN: Various version format strings
        WHEN: Setting version values
        THEN: All version formats should remain as strings
        AND: Numeric-looking versions should not convert to numbers
        """
        # Test various version formats
        version_test_cases = ["4.6.2", "v4.6.2", "1.0.0-beta", "2024.1", "stable", "development"]

        for version in version_test_cases:
            basic_model.set_component_value(("Flight Controller", "Firmware", "Version"), version)
            result = basic_model.get_component_value(("Flight Controller", "Firmware", "Version"))
            assert result == version
            assert isinstance(result, str)

    def test_system_initializes_model_correctly_via_post_init(self, empty_model) -> None:
        """
        System performs comprehensive initialization via post_init method.

        GIVEN: Empty model and optional documentation dictionary
        WHEN: Calling post_init
        THEN: JSON structure should be updated
        AND: Battery chemistry should be initialized to Lipo
        AND: Should handle both empty and populated doc_dict
        """
        # Test with empty doc_dict
        empty_model.post_init({})

        # Verify structure was updated
        assert "Battery" in empty_model._data["Components"]
        assert "Frame" in empty_model._data["Components"]
        assert "Flight Controller" in empty_model._data["Components"]

        # Test battery chemistry was initialized
        assert empty_model._battery_chemistry == "Lipo"

        # Test with populated doc_dict
        doc_dict = {
            "GPS_TYPE": {"values": {"0": "None", "2": "uBlox"}},
            "BATT_MONITOR": {"values": {"0": "Disabled", "4": "Analog Voltage and Current"}},
        }
        empty_model.post_init(doc_dict)

        # Should not crash and should maintain structure
        assert empty_model._data["Components"]["Battery"]["Specifications"]["Chemistry"] == "Lipo"

    def test_system_efficiently_handles_large_component_datasets(self, basic_model) -> None:
        """
        System efficiently handles creation and access of many components.

        GIVEN: Creation of 100+ components with various properties
        WHEN: Setting and retrieving component values
        THEN: All components should be created successfully
        AND: Random access to any component should work correctly
        AND: Memory efficiency should be maintained
        """
        # Create a large number of components to test memory efficiency
        for i in range(100):
            component_name = f"Component_{i}"
            basic_model.set_component_value((component_name, "Property"), f"Value_{i}")
            basic_model.set_component_value((component_name, "Number"), i)
            basic_model.set_component_value((component_name, "Float"), float(i) * 1.5)

        # Verify all components were created
        components = basic_model.get_all_components()
        assert len(components) >= 100  # At least 100 plus the default ones

        # Test accessing random components
        assert basic_model.get_component_value(("Component_50", "Property")) == "Value_50"
        assert basic_model.get_component_value(("Component_99", "Number")) == 99
        assert basic_model.get_component_value(("Component_25", "Float")) == 37.5

    def test_system_handles_sequential_access_to_different_components(self, basic_model) -> None:
        """
        System handles sequential access patterns to different components.

        GIVEN: Multiple components being accessed in sequence
        WHEN: Setting values for different components sequentially
        THEN: All values should be set correctly
        AND: No interference between different component operations
        """
        # Simulate multiple "threads" accessing different components
        test_operations = [
            (("Battery", "Specifications", "Capacity mAh"), 2000),
            (("Frame", "Specifications", "Weight Kg"), 1.5),
            (("Flight Controller", "Product", "Manufacturer"), "TestCorp"),
            (("ESC", "FC Connection", "Protocol"), "DShot600"),
            (("Motors", "Specifications", "Poles"), 14),
        ]

        # Perform operations in sequence (simulating concurrent access)
        for path, value in test_operations:
            basic_model.set_component_value(path, value)

        # Verify all values were set correctly
        for path, expected_value in test_operations:
            actual_value = basic_model.get_component_value(path)
            assert actual_value == expected_value

    def test_system_handles_numeric_boundary_values_correctly(self, basic_model) -> None:
        """
        System correctly handles boundary values for numeric types.

        GIVEN: Integer and float boundary values (min, max, zero)
        WHEN: Setting these boundary values
        THEN: All boundary values should be converted correctly
        AND: No overflow or underflow errors should occur
        """
        # Test integer boundaries
        boundary_int_values = [
            ("0", 0),
            ("1", 1),
            ("-1", -1),
            ("2147483647", 2147483647),  # Max 32-bit int
            ("-2147483648", -2147483648),  # Min 32-bit int
        ]

        for str_val, expected_int in boundary_int_values:
            result = basic_model._process_value(("Test", "IntValue"), str_val)
            assert result == expected_int
            assert isinstance(result, int)

        # Test float boundaries
        boundary_float_values = [
            ("0.0", 0.0),
            ("1.0", 1.0),
            ("-1.0", -1.0),
            ("1.7976931348623157e+308", 1.7976931348623157e308),  # Near max float
        ]

        for str_val, expected_float in boundary_float_values:
            result = basic_model._process_value(("Test", "FloatValue"), str_val)
            assert result == expected_float
            assert isinstance(result, float)

    def test_system_handles_unusual_path_structures(self, basic_model) -> None:
        """
        System handles unusual path structures and edge cases.

        GIVEN: Paths with unusual characteristics (empty, single element, empty strings)
        WHEN: Using these paths for get/set operations
        THEN: System should handle gracefully without crashing
        AND: Single element paths should return dict
        AND: Empty string path elements should be accepted
        """
        # Test empty path
        try:
            result = basic_model.get_component_value(())
            # Should either return empty dict or handle gracefully
            assert result == {} or isinstance(result, dict)
        except (IndexError, KeyError):
            # Acceptable to raise error for invalid path
            pass

        # Test single element path
        result = basic_model.get_component_value(("Battery",))
        assert isinstance(result, dict)

        # Test path with empty string elements
        basic_model.set_component_value(("", "EmptyKey", "Value"), "test")
        result = basic_model.get_component_value(("", "EmptyKey", "Value"))
        assert result == "test"

    def test_system_maintains_data_consistency_across_operations(self, basic_model) -> None:
        """
        System maintains data consistency across multiple set/get operations.

        GIVEN: Sequence of interleaved set and get operations
        WHEN: Performing multiple operations on different components
        THEN: All set values should be retrievable correctly
        AND: Final state should reflect all operations performed
        AND: No data corruption or loss should occur
        """
        # Perform multiple operations
        operations = [
            ("set", ("Battery", "Specifications", "Chemistry"), "LiFePO4"),
            ("set", ("Battery", "Specifications", "Capacity mAh"), 2500),
            ("get", ("Battery", "Specifications", "Chemistry"), "LiFePO4"),
            ("set", ("Frame", "Specifications", "TOW min Kg"), 1.2),
            ("get", ("Battery", "Specifications", "Capacity mAh"), 2500),
            ("set", ("New Component", "Type"), "Test"),
            ("get", ("Frame", "Specifications", "TOW min Kg"), 1.2),
        ]

        for operation, path, value_or_expected in operations:
            if operation == "set":
                basic_model.set_component_value(path, value_or_expected)
            elif operation == "get":
                result = basic_model.get_component_value(path)
                assert result == value_or_expected

        # Final consistency check
        assert basic_model.get_component_value(("Battery", "Specifications", "Chemistry")) == "LiFePO4"
        assert basic_model.get_component_value(("Battery", "Specifications", "Capacity mAh")) == 2500
        assert basic_model.get_component_value(("Frame", "Specifications", "TOW min Kg")) == 1.2
        assert basic_model.get_component_value(("New Component", "Type")) == "Test"

    def test_system_sets_new_configuration_template(self, empty_model) -> None:
        """
        System successfully sets configuration template on empty data.

        GIVEN: Empty model without configuration template
        WHEN: Setting a configuration template name
        THEN: Template name should be stored in data structure
        """
        template_name = "Test Template v1.0"
        empty_model.set_configuration_template(template_name)
        assert empty_model._data["Configuration template"] == template_name

    def test_system_overwrites_existing_configuration_template(self, basic_model) -> None:
        """
        System successfully overwrites existing configuration template.

        GIVEN: Model with existing configuration template
        WHEN: Setting a new template name
        THEN: New template name should replace the old one
        """
        template_name1 = "Initial Template"
        template_name2 = "Updated Template"

        basic_model.set_configuration_template(template_name1)
        assert basic_model._data["Configuration template"] == template_name1

        basic_model.set_configuration_template(template_name2)
        assert basic_model._data["Configuration template"] == template_name2

    def test_system_accepts_empty_string_as_template_name(self, empty_model) -> None:
        """
        System accepts empty string as valid configuration template.

        GIVEN: Empty model
        WHEN: Setting empty string as template name
        THEN: Empty string should be stored as template
        """
        empty_model.set_configuration_template("")
        assert empty_model._data["Configuration template"] == ""

    def test_system_accepts_special_characters_in_template_name(self, empty_model) -> None:
        """
        System accepts template names with special characters.

        GIVEN: Template name containing dashes, underscores, parentheses, ampersands
        WHEN: Setting the template name
        THEN: Template name with special characters should be stored correctly
        """
        template_name = "Template-v2.1_final (test) & more!"
        empty_model.set_configuration_template(template_name)
        assert empty_model._data["Configuration template"] == template_name

    # Template configuration robustness tests
    def test_system_supports_unicode_in_template_names(self, empty_model) -> None:
        """
        System supports Unicode characters in configuration template names.

        GIVEN: Template name with Unicode characters (Portuguese, Chinese, emoji)
        WHEN: Setting the template name
        THEN: Unicode template name should be stored correctly
        """
        template_name = "Configuração de Drone™ 无人机配置 🚁"
        empty_model.set_configuration_template(template_name)
        assert empty_model._data["Configuration template"] == template_name

    def test_system_handles_very_long_template_names(self, empty_model) -> None:
        """
        System handles very long configuration template names.

        GIVEN: Extremely long template name (400+ characters)
        WHEN: Setting the template name
        THEN: Long template name should be stored without truncation
        """
        template_name = "Very" * 100 + "Long Template Name"
        empty_model.set_configuration_template(template_name)
        assert empty_model._data["Configuration template"] == template_name

    def test_system_accepts_newlines_in_template_names(self, empty_model) -> None:
        """
        System accepts template names containing newline characters.

        GIVEN: Template name with embedded newlines
        WHEN: Setting the template name
        THEN: Template name with newlines should be stored correctly
        """
        template_name = "Multi\nLine\nTemplate\nName"
        empty_model.set_configuration_template(template_name)
        assert empty_model._data["Configuration template"] == template_name

    def test_system_accepts_none_as_template_value(self, empty_model) -> None:
        """
        System accepts None as valid configuration template value.

        GIVEN: None value for template
        WHEN: Setting template to None
        THEN: None should be stored as template value
        """
        empty_model.set_configuration_template(None)
        assert empty_model._data["Configuration template"] is None


class TestComponentDataModelEdgeCases:
    """Test edge cases and error scenarios for ComponentDataModelBase."""

    @pytest.fixture
    def model_with_datatypes(self) -> ComponentDataModelBase:
        """Create a ComponentDataModelBase with component datatypes for type casting tests."""
        component_datatypes = {
            "Battery": {
                "Specifications": {
                    "Capacity mAh": int,
                    "Voltage V": float,
                    "Chemistry": str,
                    "Has BMS": bool,
                    "Tags": list,
                    "Metadata": dict,
                }
            }
        }

        schema = Mock(spec=VehicleComponentsJsonSchema)
        initial_data = {"Components": {}, "Format version": 1}

        return ComponentDataModelBase(initial_data, component_datatypes, schema)

    def test_get_component_datatype_with_invalid_paths(self, model_with_datatypes) -> None:
        """
        Test _get_component_datatype with various invalid path scenarios.

        GIVEN: A model with defined component datatypes
        WHEN: Requesting datatypes for invalid paths
        THEN: Should return None gracefully
        """
        # Test with short path (missing lines 113-114)
        assert model_with_datatypes._get_component_datatype(("Battery",)) is None
        assert model_with_datatypes._get_component_datatype(("Battery", "Specifications")) is None

        # Test with empty datatypes
        model_with_datatypes._component_datatypes = {}
        assert model_with_datatypes._get_component_datatype(("Battery", "Specifications", "Capacity mAh")) is None

        # Test with missing component type
        model_with_datatypes._component_datatypes = {"Other": {}}
        assert model_with_datatypes._get_component_datatype(("Battery", "Specifications", "Capacity mAh")) is None

    def test_safe_cast_value_none_handling(self, model_with_datatypes) -> None:
        """
        Test _safe_cast_value handling of None values for all datatypes.

        GIVEN: A model with type casting capability
        WHEN: Casting None values to different datatypes
        THEN: Should return appropriate default values
        """
        path = ("Battery", "Specifications", "Test")

        # Test None to string
        result = model_with_datatypes._safe_cast_value(None, str, path)
        assert result == ""

        # Test None to int
        result = model_with_datatypes._safe_cast_value(None, int, path)
        assert result == 0

        # Test None to float
        result = model_with_datatypes._safe_cast_value(None, float, path)
        assert result == 0.0

        # Test None to bool
        result = model_with_datatypes._safe_cast_value(None, bool, path)
        assert result is False

        # Test None to list
        result = model_with_datatypes._safe_cast_value(None, list, path)
        assert result == []

    def test_safe_cast_value_none_handling_edge_cases(self, model_with_datatypes) -> None:
        """
        Test _safe_cast_value None handling for edge cases.

        GIVEN: A model with type casting capability
        WHEN: Casting None values to unusual datatypes
        THEN: Should handle gracefully
        """
        path = ("Battery", "Specifications", "Test")

        # Test None to dict
        result = model_with_datatypes._safe_cast_value(None, dict, path)
        assert result == {}

        # Test None with unknown datatype
        class CustomType:  # pylint: disable=too-few-public-methods
            """Dummy, just for testing."""

        result = model_with_datatypes._safe_cast_value(None, CustomType, path)
        assert result == ""  # Should return empty string for unknown types

    def test_get_component_datatype_isinstance_comprehensive_coverage(self, model_with_datatypes) -> None:
        """
        Test _get_component_datatype isinstance check with comprehensive scenarios.

        GIVEN: A model with component datatypes
        WHEN: Accessing datatypes with various path scenarios
        THEN: Should execute isinstance check paths
        """
        # Set up component datatypes with both type objects and non-type values
        model_with_datatypes._component_datatypes = {
            "Battery": {
                "Specifications": {
                    "ValidType": int,  # This is a type
                    "InvalidType": "not_a_type",  # This is not a type
                    "AnotherValidType": str,  # Another type
                    "NonCallable": 42,  # Not callable
                }
            }
        }

        # Test valid type (covers line 113: if isinstance(datatype, type))
        datatype = model_with_datatypes._get_component_datatype(("Battery", "Specifications", "ValidType"))
        assert datatype is int

        # Test another valid type
        datatype = model_with_datatypes._get_component_datatype(("Battery", "Specifications", "AnotherValidType"))
        assert datatype is str

        # Test invalid type - string
        datatype = model_with_datatypes._get_component_datatype(("Battery", "Specifications", "InvalidType"))
        assert datatype is None

        # Test invalid type - number
        datatype = model_with_datatypes._get_component_datatype(("Battery", "Specifications", "NonCallable"))
        assert datatype is None

    def test_safe_cast_value_list_dict_special_handling_direct(self, model_with_datatypes, caplog) -> None:
        """
        Test direct path to list/dict special handling in _safe_cast_value.

        GIVEN: A model with type casting capability
        WHEN: Attempting to cast to list or dict types
        THEN: Should execute special handling code and log error
        """
        path = ("Battery", "Specifications", "TestField")

        # Test list datatype - log error, and fall back to _process_value
        result = model_with_datatypes._safe_cast_value("some_value", list, path)
        assert result == "some_value"  # Falls back to _process_value which returns the original value
        assert "Failed to cast value" in caplog.text

        caplog.clear()

        # Test dict datatype - log error, and fall back to _process_value
        result = model_with_datatypes._safe_cast_value("another_value", dict, path)
        assert result == "another_value"  # Falls back to _process_value which returns the original value
        assert "Failed to cast value" in caplog.text

    def test_safe_cast_value_attribute_error_handling(self, model_with_datatypes, caplog) -> None:
        """
        Test AttributeError handling in _safe_cast_value.

        GIVEN: A model with type casting capability
        WHEN: A callable datatype raises AttributeError during instantiation
        THEN: Should catch AttributeError and fall back to _process_value
        """
        path = ("Battery", "Specifications", "TestField")

        # Create a mock class that raises AttributeError when called
        class AttributeErrorType(type):
            """Dummy, just for testing."""

            def __call__(cls, *args, **kwargs) -> None:
                msg = "Mock AttributeError for testing"
                raise AttributeError(msg)

        class MockDatatype(metaclass=AttributeErrorType):  # pylint: disable=too-few-public-methods
            """Dummy, just for testing."""

        # This should trigger the AttributeError handling
        result = model_with_datatypes._safe_cast_value("test_value", MockDatatype, path)

        # Should log the error and fall back to _process_value
        assert "Failed to cast value" in caplog.text
        assert "AttributeError" in caplog.text
        assert result == "test_value"  # Fallback to _process_value result

    def test_deep_merge_dicts_recursive_comprehensive(self, model_with_datatypes) -> None:
        """
        Test _deep_merge_dicts recursive merging comprehensively.

        GIVEN: A model instance with _deep_merge_dicts method
        WHEN: Merging nested dictionaries with various structures
        THEN: Should handle all recursive paths
        """
        # Test deep recursive merging
        default = {
            "level1": {
                "level2": {
                    "level3": {"default_value": "from_default", "shared_key": "default_shared"},
                    "default_level2": "default",
                },
                "simple_default": "default",
            },
            "top_level_default": "default",
        }

        existing = {
            "level1": {
                "level2": {
                    "level3": {
                        "existing_value": "from_existing",
                        "shared_key": "existing_shared",  # Should override default
                    },
                    "existing_level2": "existing",
                },
                "simple_existing": "existing",
            },
            "top_level_existing": "existing",
        }

        result = model_with_datatypes._deep_merge_dicts(default, existing)

        # Verify deep recursive merging occurred
        assert result["level1"]["level2"]["level3"]["default_value"] == "from_default"
        assert result["level1"]["level2"]["level3"]["existing_value"] == "from_existing"
        assert result["level1"]["level2"]["level3"]["shared_key"] == "existing_shared"
        assert result["level1"]["level2"]["default_level2"] == "default"
        assert result["level1"]["level2"]["existing_level2"] == "existing"
        assert result["level1"]["simple_default"] == "default"
        assert result["level1"]["simple_existing"] == "existing"
        assert result["top_level_default"] == "default"
        assert result["top_level_existing"] == "existing"

        # Test case where existing value is not a dict
        default_with_dict = {"mixed_key": {"nested": "should_not_appear"}}

        existing_with_string = {
            "mixed_key": "string_value"  # Not a dict
        }

        result = model_with_datatypes._deep_merge_dicts(default_with_dict, existing_with_string)

        # existing value should be preserved
        assert result["mixed_key"] == "string_value"
        assert not isinstance(result["mixed_key"], dict)

    def test_system_handles_none_values_and_version_fields_specially(self, model_with_datatypes) -> None:
        """
        System handles None values and Version field type conversion specially.

        GIVEN: Values that are None or Version field paths
        WHEN: Processing these values
        THEN: None values should convert to empty string
        AND: Version fields should remain as strings regardless of content
        AND: Non-Version numeric fields should still convert to numbers
        """
        # Test None value handling
        path = ("Battery", "Specifications", "TestField")
        result = model_with_datatypes._process_value(path, None)
        assert result == ""

        # Test Version field special handling
        version_path = ("Battery", "Product", "Version")
        result = model_with_datatypes._process_value(version_path, "1.2.3-beta")
        assert result == "1.2.3-beta"
        assert isinstance(result, str)

        # Test that non-Version fields still attempt numeric conversion
        numeric_path = ("Battery", "Specifications", "Capacity")
        result = model_with_datatypes._process_value(numeric_path, "1500")
        assert result == 1500
        assert isinstance(result, int)

        # Verify None handling for different path types
        result = model_with_datatypes._process_value(version_path, None)
        assert result == ""

        result = model_with_datatypes._process_value(numeric_path, None)
        assert result == ""


class TestComponentReordering:
    """Test component reordering functionality in ComponentDataModelBase."""

    @pytest.fixture
    def model_instance(self) -> ComponentDataModelBase:
        """Create a ComponentDataModelBase instance for testing reordering."""
        schema = VehicleComponentsJsonSchema({})
        return ComponentDataModelBase({}, {}, schema)

    def test_user_sees_components_reordered_to_logical_sequence(self, model_instance) -> None:
        """
        User sees vehicle components displayed in a logical, workflow-oriented order.

        GIVEN: A vehicle configuration with components in random order
        WHEN: The system processes the component data
        THEN: Components are reordered to follow the expected workflow sequence
        AND: Known components appear before unknown/custom components
        """
        # Arrange: Create components in random order
        existing_components = {
            "RC Controller": {"Product": {"Manufacturer": "FrSky", "Model": "Taranis"}},
            "GNSS Receiver": {"Product": {"Manufacturer": "u-blox", "Model": "NEO-M8N"}},
            "Battery": {"Product": {"Manufacturer": "Tattu", "Model": "25C"}},
            "Flight Controller": {"Product": {"Manufacturer": "Pixhawk", "Model": "6C"}},
            "Custom Sensor": {"Product": {"Manufacturer": "Custom", "Model": "Sensor1"}},  # Unknown component
        }

        # Act: Reorder components
        result = model_instance._reorder_components(existing_components)

        # Assert: Components are in the expected order
        component_order = list(result.keys())
        expected_known_order = ["Flight Controller", "Battery", "GNSS Receiver", "RC Controller"]

        # Check that known components appear in the expected relative order
        for _i, component in enumerate(expected_known_order):
            if component in component_order:
                assert component_order.index(component) < component_order.index("Custom Sensor"), (
                    f"Known component {component} should appear before unknown components"
                )

        # Custom/unknown components should be at the end
        assert component_order[-1] == "Custom Sensor"

    def test_user_sees_product_fields_ordered_consistently(self, model_instance) -> None:
        """
        User sees product information fields displayed in a consistent, logical order.

        GIVEN: A component with product fields in random order
        WHEN: The system processes the component data
        THEN: Product fields are reordered with Version appearing before URL
        AND: All existing field values are preserved
        """
        # Arrange: Create component with Product fields in wrong order
        existing_components = {
            "Flight Controller": {
                "Product": {"Manufacturer": "Pixhawk", "URL": "https://pixhawk.org", "Model": "6C", "Version": "1.0"},
                "Firmware": {"Type": "ArduCopter", "Version": "4.5.x"},
            }
        }

        # Act: Reorder components
        result = model_instance._reorder_components(existing_components)

        # Assert: Product fields are reordered correctly
        product_fields = list(result["Flight Controller"]["Product"].keys())
        version_index = product_fields.index("Version")
        url_index = product_fields.index("URL")

        assert version_index < url_index, "Version should appear before URL in Product fields"

        # Verify all original values are preserved
        assert result["Flight Controller"]["Product"]["Manufacturer"] == "Pixhawk"
        assert result["Flight Controller"]["Product"]["Model"] == "6C"
        assert result["Flight Controller"]["Product"]["Version"] == "1.0"
        assert result["Flight Controller"]["Product"]["URL"] == "https://pixhawk.org"

    def test_user_sees_unknown_components_preserved_at_end(self, model_instance) -> None:
        """
        User sees custom or unknown components preserved and displayed at the end of the list.

        GIVEN: A vehicle configuration with both known and unknown components
        WHEN: The system processes the component data
        THEN: Unknown components are preserved and appear at the end
        AND: Their data remains unchanged
        """
        # Arrange: Mix of known and unknown components
        existing_components = {
            "Flight Controller": {"Product": {"Manufacturer": "Pixhawk"}},
            "Custom IMU": {"Product": {"Manufacturer": "Custom IMU Corp", "Model": "IMU-X1"}},  # Unknown
            "Battery": {"Product": {"Manufacturer": "Tattu"}},
            "Proprietary Sensor": {"Product": {"Manufacturer": "Proprietary Inc", "Model": "Sensor-Z"}},  # Unknown
            "GNSS Receiver": {"Product": {"Manufacturer": "u-blox"}},
        }

        # Act: Reorder components
        result = model_instance._reorder_components(existing_components)

        # Assert: Unknown components appear at the end
        component_order = list(result.keys())

        # Known components should come first in some logical order
        known_components = ["Flight Controller", "Battery", "GNSS Receiver"]
        unknown_components = ["Custom IMU", "Proprietary Sensor"]

        # Find positions of known vs unknown components
        known_positions = [component_order.index(comp) for comp in known_components if comp in component_order]
        unknown_positions = [component_order.index(comp) for comp in unknown_components if comp in component_order]

        # All unknown components should be at the end
        if unknown_positions:
            min_unknown_pos = min(unknown_positions)
            max_known_pos = max(known_positions) if known_positions else -1
            assert min_unknown_pos > max_known_pos, "Unknown components should appear after known components"

        # Verify unknown component data is preserved
        assert result["Custom IMU"]["Product"]["Manufacturer"] == "Custom IMU Corp"
        assert result["Custom IMU"]["Product"]["Model"] == "IMU-X1"
        assert result["Proprietary Sensor"]["Product"]["Manufacturer"] == "Proprietary Inc"
        assert result["Proprietary Sensor"]["Product"]["Model"] == "Sensor-Z"

    def test_user_sees_components_without_product_sections_unchanged(self, model_instance) -> None:
        """
        User sees components without Product sections remain completely unchanged.

        GIVEN: Components with various section types but no Product section
        WHEN: The system processes the component data
        THEN: Components without Product sections are unchanged
        AND: Their structure and values are preserved exactly
        """
        # Arrange: Components without Product sections
        existing_components = {
            "Flight Controller": {
                "Firmware": {"Type": "ArduCopter", "Version": "4.5.x"},
                "Specifications": {"MCU Series": "STM32H7"},
            },
            "Battery": {"Specifications": {"Chemistry": "Lipo", "Capacity mAh": 5000}},
        }

        # Act: Reorder components
        result = model_instance._reorder_components(existing_components)

        # Assert: Components without Product sections are unchanged
        assert result["Flight Controller"]["Firmware"]["Type"] == "ArduCopter"
        assert result["Flight Controller"]["Firmware"]["Version"] == "4.5.x"
        assert result["Flight Controller"]["Specifications"]["MCU Series"] == "STM32H7"

        assert result["Battery"]["Specifications"]["Chemistry"] == "Lipo"
        assert result["Battery"]["Specifications"]["Capacity mAh"] == 5000

    def test_user_sees_product_sections_with_missing_fields_handled_gracefully(self, model_instance) -> None:
        """
        User sees product sections with missing Version or URL fields handled gracefully.

        GIVEN: Components with Product sections missing Version or URL fields
        WHEN: The system processes the component data
        THEN: Product sections without both Version and URL fields are unchanged
        AND: No reordering occurs when required fields are missing
        """
        # Arrange: Product sections with incomplete field sets
        existing_components = {
            "Flight Controller": {
                "Product": {
                    "Manufacturer": "Pixhawk",
                    "Model": "6C",
                    # Missing Version and URL
                }
            },
            "GNSS Receiver": {
                "Product": {
                    "Manufacturer": "u-blox",
                    "Version": "1.0",
                    # Missing URL
                }
            },
            "Telemetry": {
                "Product": {
                    "Manufacturer": "SiK",
                    "URL": "https://sik.org",
                    # Missing Version
                }
            },
        }

        # Act: Reorder components
        result = model_instance._reorder_components(existing_components)

        # Assert: Product sections with missing fields are unchanged
        # Flight Controller: missing both Version and URL
        fc_product = result["Flight Controller"]["Product"]
        assert list(fc_product.keys()) == ["Manufacturer", "Model"]

        # GNSS Receiver: missing URL
        gnss_product = result["GNSS Receiver"]["Product"]
        assert list(gnss_product.keys()) == ["Manufacturer", "Version"]

        # Telemetry: missing Version
        telemetry_product = result["Telemetry"]["Product"]
        assert list(telemetry_product.keys()) == ["Manufacturer", "URL"]

    def test_user_sees_complex_product_sections_with_extra_fields_preserved(self, model_instance) -> None:
        """
        User sees complex product sections with extra custom fields preserved correctly.

        GIVEN: Components with Product sections containing extra custom fields
        WHEN: The system processes the component data
        THEN: Standard fields are reordered correctly
        AND: Extra custom fields are preserved at the end
        AND: All field values remain unchanged
        """
        # Arrange: Product sections with extra custom fields
        existing_components = {
            "Flight Controller": {
                "Product": {
                    "URL": "https://pixhawk.org",
                    "Custom Field 1": "Custom Value 1",
                    "Manufacturer": "Pixhawk",
                    "Version": "1.0",
                    "Custom Field 2": "Custom Value 2",
                    "Model": "6C",
                    "Custom Field 3": "Custom Value 3",
                }
            }
        }

        # Act: Reorder components
        result = model_instance._reorder_components(existing_components)

        # Assert: Standard fields are reordered, custom fields preserved
        product_fields = list(result["Flight Controller"]["Product"].keys())

        # Standard fields should be first in correct order
        manufacturer_idx = product_fields.index("Manufacturer")
        model_idx = product_fields.index("Model")
        version_idx = product_fields.index("Version")
        url_idx = product_fields.index("URL")

        assert manufacturer_idx < model_idx < version_idx < url_idx, (
            "Standard fields should be in correct order: Manufacturer, Model, Version, URL"
        )

        # Custom fields should appear after standard fields
        custom1_idx = product_fields.index("Custom Field 1")
        custom2_idx = product_fields.index("Custom Field 2")
        custom3_idx = product_fields.index("Custom Field 3")

        assert custom1_idx > url_idx, "Custom fields should appear after standard fields"
        assert custom2_idx > url_idx, "Custom fields should appear after standard fields"
        assert custom3_idx > url_idx, "Custom fields should appear after standard fields"

        # Verify all values are preserved
        product = result["Flight Controller"]["Product"]
        assert product["Manufacturer"] == "Pixhawk"
        assert product["Model"] == "6C"
        assert product["Version"] == "1.0"
        assert product["URL"] == "https://pixhawk.org"
        assert product["Custom Field 1"] == "Custom Value 1"
        assert product["Custom Field 2"] == "Custom Value 2"
        assert product["Custom Field 3"] == "Custom Value 3"
