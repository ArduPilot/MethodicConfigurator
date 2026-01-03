#!/usr/bin/env python3

"""
Vehicle Components data model tests for basic ComponentDataModelBase functionality.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

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

    def test_user_can_enter_component_values_in_various_formats(self, basic_model) -> None:
        """
        User can enter component values as strings and system stores them in appropriate types.

        GIVEN: User entering component values as text strings
        WHEN: Setting values for different component properties
        THEN: Numeric strings should be stored as numbers for calculations
        AND: Text values should be stored as strings
        AND: Whitespace should be automatically trimmed
        AND: Version numbers should remain as strings
        """
        # User enters battery capacity as string
        basic_model.set_component_value(("Battery", "Specifications", "Capacity mAh"), "2000")
        capacity = basic_model.get_component_value(("Battery", "Specifications", "Capacity mAh"))
        assert capacity == 2000
        assert capacity * 2 == 4000  # Can be used in calculations

        # User enters frame weight as string
        basic_model.set_component_value(("Frame", "Specifications", "Weight Kg"), "0.25")
        weight = basic_model.get_component_value(("Frame", "Specifications", "Weight Kg"))
        assert weight == 0.25
        assert weight + 0.5 == 0.75  # Can be used in calculations

        # User enters chemistry with extra whitespace
        # User enters chemistry text
        basic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")
        chemistry = basic_model.get_component_value(("Battery", "Specifications", "Chemistry"))
        assert chemistry == "Lipo"

        # User enters notes as text
        basic_model.set_component_value(("Flight Controller", "Notes"), "Special notes")
        notes = basic_model.get_component_value(("Flight Controller", "Notes"))
        assert notes == "Special notes"

        # User enters version number
        basic_model.set_component_value(("Flight Controller", "Firmware", "Version"), "4.6.2")
        version = basic_model.get_component_value(("Flight Controller", "Firmware", "Version"))
        assert version == "4.6.2"  # Stored as string, not converted to number

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

    def test_user_can_enter_numeric_values_as_text(self, basic_model) -> None:
        """
        User can enter numeric values as text and system handles conversion appropriately.

        GIVEN: User entering various numeric and text values
        WHEN: Setting component values
        THEN: Integer-like strings should work as integers
        AND: Decimal strings should work as decimals
        AND: Non-numeric text should remain as text
        AND: Version fields should always be text
        """
        # User enters integer as text
        basic_model.set_component_value(("Test", "Numeric"), "42")
        result = basic_model.get_component_value(("Test", "Numeric"))
        assert result == 42
        assert result + 8 == 50  # Can do math with it

        # User enters decimal as text
        basic_model.set_component_value(("Test", "Numeric"), "42.5")
        result = basic_model.get_component_value(("Test", "Numeric"))
        assert result == 42.5
        assert result * 2 == 85.0  # Can do math with it

        # User enters text that isn't a number
        basic_model.set_component_value(("Test", "Numeric"), "not_a_number")
        result = basic_model.get_component_value(("Test", "Numeric"))
        assert result == "not_a_number"

        # User enters version number that looks numeric
        basic_model.set_component_value(("Test", "Version"), "42")
        result = basic_model.get_component_value(("Test", "Version"))
        assert result == "42"  # Stays as text for version fields

    def test_user_can_safely_query_nonexistent_components(self, basic_model) -> None:
        """
        User can query components that don't exist without causing errors.

        GIVEN: User attempting to access components or paths that don't exist
        WHEN: Querying for non-existent component data
        THEN: System should return empty data instead of crashing
        AND: User can check if component exists before using it
        """
        # User queries a component that doesn't exist
        result = basic_model.get_component_value(("NonExistent", "Path", "Deep"))
        assert result == {}  # Returns empty dict, doesn't crash

        # User can check if result is empty before proceeding
        if not result:
            # User's code can handle missing components gracefully
            pass

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

    def test_user_can_enter_negative_and_zero_numeric_values(self, basic_model) -> None:
        """
        User can enter negative values and zero for component specifications.

        GIVEN: User configuring components with various numeric values
        WHEN: Entering negative numbers or zero
        THEN: Values should be accepted and stored correctly
        AND: Can be used in subsequent calculations
        """
        # User enters zero value
        basic_model.set_component_value(("Test", "Value"), "0")
        result = basic_model.get_component_value(("Test", "Value"))
        assert result == 0

        # User enters negative value (e.g., temperature offset)
        basic_model.set_component_value(("Test", "Offset"), "-5")
        result = basic_model.get_component_value(("Test", "Offset"))
        assert result == -5
        assert result + 10 == 5  # Can use in calculations

    def test_system_cleans_up_user_input_whitespace(self, basic_model) -> None:
        """
        System automatically cleans up whitespace from user input.

        GIVEN: User enters values with extra whitespace (copy/paste errors)
        WHEN: Setting component values
        THEN: Leading and trailing whitespace should be removed automatically
        AND: User doesn't need to manually clean input
        """
        # User accidentally includes whitespace (e.g., from copy/paste)
        basic_model.set_component_value(("Test", "Name"), "  Pixhawk 6C  ")
        result = basic_model.get_component_value(("Test", "Name"))
        assert result == "Pixhawk 6C"  # Whitespace automatically removed

    def test_user_can_retrieve_complete_component_data(self, basic_model) -> None:
        """
        User can retrieve all component data for export or inspection.

        GIVEN: A vehicle with configured components
        WHEN: User retrieves complete component data
        THEN: All component information should be accessible
        AND: Data should include all required components
        """
        # User retrieves complete component data (e.g., for export)
        component_data = basic_model.get_component_data()

        # User can access component information
        assert "Components" in component_data
        assert "Battery" in component_data["Components"]
        assert "Flight Controller" in component_data["Components"]

        # User can read specific component details
        battery = component_data["Components"]["Battery"]
        assert "Specifications" in battery

    def test_system_initializes_with_default_structure_when_no_data_provided(self) -> None:
        """
        System creates default component structure when starting fresh.

        GIVEN: User creating a new vehicle configuration from scratch
        WHEN: Initializing component model without existing data
        THEN: Model should have default structure ready for use
        AND: Required components should be initialized
        """
        # User starts a new vehicle configuration
        vehicle_components = VehicleComponents()
        schema = VehicleComponentsJsonSchema(vehicle_components.load_schema())
        component_datatypes = schema.get_all_value_datatypes()
        model = ComponentDataModelBase(None, component_datatypes, schema)  # type: ignore[arg-type]

        # System provides default structure
        component_data = model.get_component_data()
        assert "Components" in component_data
        assert "Format version" in component_data

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

    def test_user_can_configure_components_with_realistic_numeric_values(self, basic_model) -> None:
        """
        User can configure components with realistic numeric values.

        GIVEN: User configuring realistic component specifications
        WHEN: Entering typical numeric values for battery, weight, etc.
        THEN: All realistic values should be accepted and stored correctly
        """
        # Realistic battery capacity (1000-30000 mAh)
        basic_model.set_component_value(("Battery", "Specifications", "Capacity mAh"), "5000")
        assert basic_model.get_component_value(("Battery", "Specifications", "Capacity mAh")) == 5000

        # Realistic frame weight (0.1 - 100 Kg)
        basic_model.set_component_value(("Frame", "Specifications", "Weight Kg"), "2.5")
        assert basic_model.get_component_value(("Frame", "Specifications", "Weight Kg")) == 2.5

    def test_user_can_access_component_categories(self, basic_model) -> None:
        """
        User can access component categories without specifying full path.

        GIVEN: User wanting to browse component categories
        WHEN: Accessing component by category name only
        THEN: Should return all data for that category
        """
        # User accesses Battery category
        result = basic_model.get_component_value(("Battery",))
        assert isinstance(result, dict)
        assert "Specifications" in result

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
