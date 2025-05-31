#!/usr/bin/env python3

"""
Vehicle Components data model tests for basic ComponentDataModelBase functionality.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock, Mock

import pytest
from test_data_model_vehicle_components_common import BasicTestMixin, ComponentDataModelFixtures, RealisticDataTestMixin

from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents
from ardupilot_methodic_configurator.data_model_vehicle_components_base import ComponentData, ComponentDataModelBase

# pylint: disable=protected-access,too-many-public-methods


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
    def test_set_component_value(self, basic_model) -> None:
        """Test setting a component value."""
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

    def test_get_component_value(self, basic_model) -> None:
        """Test getting a component value."""
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

    def test_set_component_value_batch(self, basic_model) -> None:
        """Test setting multiple component values."""
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

    def test_format_version_management(self, basic_model, empty_model) -> None:
        """Test format version management."""
        # Should not change existing format version
        original_version = basic_model._data["Format version"]
        # Format version should remain unchanged during normal operations
        assert basic_model._data["Format version"] == original_version

        # Empty model should have default format version
        assert empty_model._data["Format version"] == 1

    def test_process_value(self, basic_model) -> None:
        """Test processing values to the appropriate type."""
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

    def test_get_component_data_access(self, basic_model) -> None:
        """Test accessing component data."""
        # Test getting specific component's data via get_component_data
        components = basic_model.get_component_data()["Components"]
        battery_data = components.get("Battery", {})
        assert isinstance(battery_data, dict)
        assert battery_data.get("Specifications", {}).get("Chemistry") == "Lipo"
        assert battery_data.get("Specifications", {}).get("Capacity mAh") == 0

        # Test getting non-existent component
        nonexistent = components.get("NonExistent", {})
        assert nonexistent == {}

    def test_component_data_modification(self, basic_model) -> None:
        """Test modifying component data."""
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

    def test_update_json_structure(self, empty_model) -> None:
        """Test updating JSON structure for old files."""
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

    def test_rename_old_gnss_receiver_key(self, basic_model) -> None:
        """Test renaming old 'GNSS receiver' to 'GNSS Receiver'."""
        # Add old key format
        basic_model._data["Components"]["GNSS receiver"] = {"Product": {"Manufacturer": "Holybro", "Model": "H-RTK F9P"}}

        basic_model.update_json_structure()

        # Check that old key is removed and new key exists
        assert "GNSS receiver" not in basic_model._data["Components"]
        assert "GNSS Receiver" in basic_model._data["Components"]
        assert basic_model._data["Components"]["GNSS Receiver"]["Product"]["Manufacturer"] == "Holybro"

    def test_none_value_handling(self, basic_model) -> None:
        """Test handling of None values."""
        # Set None and then ensure it's converted to empty string
        basic_model.set_component_value(("Motor", "Notes"), None)
        assert basic_model.get_component_value(("Motor", "Notes")) == ""

        # Set None values individually
        basic_model.set_component_value(("Motor", "Description"), None)
        assert basic_model.get_component_value(("Motor", "Description")) == ""

    def test_edge_cases_process_value(self, basic_model) -> None:
        """Test edge cases in _process_value method."""
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

    def test_get_component_value_edge_cases(self, basic_model) -> None:
        """Test edge cases in get_component_value method."""
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

    def test_update_component_data_via_set_values(self, empty_model) -> None:
        """Test updating component when Components key doesn't exist."""
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

    def test_combobox_values_basic_functionality(self, realistic_model) -> None:
        """Test basic functionality of get_combobox_values_for_path."""
        # Test with basic path - only test with one argument since that's what the base class supports
        unknown_path = ("Unknown", "Component", "Property")
        result = realistic_model.get_combobox_values_for_path(unknown_path)
        assert result == ()  # Should return empty tuple for unknown paths

    def test_save_to_filesystem_method(self, realistic_model) -> None:
        """Test save_to_filesystem method with mocked filesystem."""
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

    def test_update_json_structure_missing_fc_data(self, realistic_model) -> None:
        """Test update_json_structure when Flight Controller has missing data."""
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

    def test_update_json_structure_missing_components(self) -> None:
        """Test JSON structure update when Components key is missing."""
        # Create data without Components key
        data: ComponentData = {"Configuration": {}}
        vehicle_components = VehicleComponents()
        component_datatypes = vehicle_components.get_all_value_datatypes()
        component_model = ComponentDataModelBase(data, component_datatypes)

        # Call update_json_structure to create the Components key
        component_model.update_json_structure()

        # Should create Components key
        assert "Components" in component_model._data
        assert "Battery" in component_model._data["Components"]
        assert "Specifications" in component_model._data["Components"]["Battery"]

    def test_update_json_structure_missing_battery(self, realistic_model) -> None:
        """Test JSON structure update when Battery component is missing."""
        # Remove Battery component
        if "Battery" in realistic_model._data["Components"]:
            del realistic_model._data["Components"]["Battery"]

        realistic_model.update_json_structure()

        # Should recreate Battery component with Specifications
        assert "Battery" in realistic_model._data["Components"]
        assert "Specifications" in realistic_model._data["Components"]["Battery"]

    def test_update_json_structure_missing_fc_subkeys_coverage(self, realistic_model) -> None:
        """Test update_json_structure when Flight Controller has missing sub-keys."""
        # Remove some Flight Controller sub-keys
        if "Specifications" in realistic_model._data["Components"]["Flight Controller"]:
            del realistic_model._data["Components"]["Flight Controller"]["Specifications"]

        realistic_model.update_json_structure()

        # Should recreate missing Specifications
        assert "Specifications" in realistic_model._data["Components"]["Flight Controller"]
        assert realistic_model._data["Components"]["Flight Controller"]["Specifications"]["MCU Series"] == "Unknown"

    def test_get_component_datatype_functionality(self, basic_model) -> None:
        """Test _get_component_datatype method thoroughly."""
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

    def test_safe_cast_value_comprehensive(self, basic_model) -> None:
        """Test _safe_cast_value method with various scenarios."""
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

    def test_data_structure_validation(self, basic_model, empty_model) -> None:
        """Test data structure validation and edge cases."""
        # Test basic structure validation
        assert isinstance(basic_model._data, dict)
        assert "Components" in basic_model._data
        assert isinstance(basic_model._data["Components"], dict)

        # Test empty structure validation
        assert isinstance(empty_model._data, dict)
        assert "Components" in empty_model._data

        # Test with corrupted data structure
        corrupted_model = ComponentDataModelBase({}, {})
        assert corrupted_model._data == {"Components": {}, "Format version": 1}

    def test_nested_path_creation(self, empty_model) -> None:
        """Test creation of deeply nested paths."""
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

    def test_type_conversion_edge_cases(self, basic_model) -> None:
        """Test edge cases in type conversion."""
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

    def test_whitespace_handling(self, basic_model) -> None:
        """Test handling of whitespace in values."""
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

    def test_component_data_immutability(self, basic_model) -> None:
        """Test that returned component data affects internal state (documents current behavior)."""
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

    def test_error_handling_malformed_data(self) -> None:
        """Test error handling with malformed initial data."""
        # Test with None initial data
        vehicle_components = VehicleComponents()
        component_datatypes = vehicle_components.get_all_value_datatypes()
        model = ComponentDataModelBase(None, component_datatypes)  # type: ignore[arg-type]
        assert model._data == {"Components": {}, "Format version": 1}

        # Test with string instead of dict - documents current behavior
        # The constructor doesn't validate input, it just assigns whatever is passed
        try:
            model = ComponentDataModelBase("invalid", component_datatypes)  # type: ignore[arg-type]
            # Current behavior: Constructor doesn't validate input type
            assert model._data == "invalid"  # Documents that no validation occurs
        except (TypeError, AttributeError):
            # If the constructor validates input and raises an error, that's also acceptable
            pass

    def test_battery_chemistry_initialization(self, basic_model) -> None:
        """Test battery chemistry initialization."""
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

    def test_component_access_patterns(self, realistic_model) -> None:
        """Test various component access patterns."""
        # Test accessing all top-level components
        components = realistic_model.get_all_components()
        assert isinstance(components, dict)
        assert len(components) > 0

        # Test has_components method
        assert realistic_model.has_components() is True

        # Test with model that has no components
        empty_components = ComponentDataModelBase({"Components": {}, "Format version": 1}, {})
        assert empty_components.has_components() is False

    def test_version_field_special_handling(self, basic_model) -> None:
        """Test special handling of Version fields."""
        # Test various version formats
        version_test_cases = ["4.6.2", "v4.6.2", "1.0.0-beta", "2024.1", "stable", "development"]

        for version in version_test_cases:
            basic_model.set_component_value(("Flight Controller", "Firmware", "Version"), version)
            result = basic_model.get_component_value(("Flight Controller", "Firmware", "Version"))
            assert result == version
            assert isinstance(result, str)

    def test_post_init_comprehensive(self, empty_model) -> None:
        """Test post_init method comprehensively."""
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

    def test_memory_efficiency_large_data(self, basic_model) -> None:
        """Test handling of large data structures."""
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

    def test_concurrent_access_simulation(self, basic_model) -> None:
        """Simulate concurrent access patterns."""
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

    def test_boundary_value_testing(self, basic_model) -> None:
        """Test boundary values for numeric conversions."""
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

    def test_path_validation_edge_cases(self, basic_model) -> None:
        """Test edge cases in path validation and traversal."""
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

    def test_data_consistency_after_operations(self, basic_model) -> None:
        """Test that data remains consistent after multiple operations."""
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
