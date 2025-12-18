#!/usr/bin/env python3

"""
Unit tests for low-level ComponentDataModelBase implementation details.

These tests verify internal methods and implementation details for coverage purposes.
For behavior-driven tests, see test_data_model_vehicle_components_base.py

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import Mock

import pytest
from test_data_model_vehicle_components_common import ComponentDataModelFixtures

from ardupilot_methodic_configurator.data_model_vehicle_components_base import ComponentDataModelBase
from ardupilot_methodic_configurator.data_model_vehicle_components_json_schema import VehicleComponentsJsonSchema

# pylint: disable=protected-access


class TestComponentDataModelBaseInternals:
    """Unit tests for ComponentDataModelBase internal methods."""

    @pytest.fixture
    def basic_model(self) -> ComponentDataModelBase:
        """Create a ComponentDataModelBase fixture for testing."""
        return ComponentDataModelFixtures.create_basic_model(ComponentDataModelBase)

    @pytest.fixture
    def model_with_datatypes(self) -> ComponentDataModelBase:
        """Create a model with test datatypes configured."""
        schema = VehicleComponentsJsonSchema({})
        model = ComponentDataModelBase({}, {}, schema)
        model._component_datatypes = {"Battery": {"Specifications": {"Capacity mAh": int, "Voltage": float, "Chemistry": str}}}
        return model

    def test_get_component_datatype_with_valid_paths(self, basic_model) -> None:
        """
        Test _get_component_datatype with valid component paths.

        GIVEN: Component paths with known datatypes
        WHEN: Requesting datatype for each path
        THEN: Correct Python type should be returned
        """
        datatype = basic_model._get_component_datatype(("Battery", "Specifications", "Capacity mAh"))
        assert datatype is int

        datatype = basic_model._get_component_datatype(("Frame", "Specifications", "TOW min Kg"))
        assert datatype is float

        datatype = basic_model._get_component_datatype(("Battery", "Specifications", "Chemistry"))
        assert datatype is str

    def test_get_component_datatype_with_invalid_paths(self, basic_model) -> None:
        """
        Test _get_component_datatype with invalid or non-existent paths.

        GIVEN: Invalid component paths
        WHEN: Requesting datatypes
        THEN: Should return None
        """
        # Non-existent path
        datatype = basic_model._get_component_datatype(("NonExistent", "Component", "Field"))
        assert datatype is None

        # Path too short
        datatype = basic_model._get_component_datatype(("Battery", "Specifications"))
        assert datatype is None

        # Empty component datatypes
        basic_model._component_datatypes = {}
        datatype = basic_model._get_component_datatype(("Battery", "Specifications", "Capacity mAh"))
        assert datatype is None

    def test_get_component_datatype_isinstance_comprehensive_coverage(self, model_with_datatypes) -> None:
        """
        Test _get_component_datatype isinstance check with comprehensive scenarios.

        GIVEN: A model with component datatypes including non-type values
        WHEN: Accessing datatypes with various path scenarios
        THEN: Should correctly identify type objects and return None for non-types
        """
        model_with_datatypes._component_datatypes = {
            "Battery": {
                "Specifications": {
                    "ValidType": int,
                    "InvalidType": "not_a_type",
                    "AnotherValidType": str,
                    "NonCallable": 42,
                }
            }
        }

        # Valid type
        datatype = model_with_datatypes._get_component_datatype(("Battery", "Specifications", "ValidType"))
        assert datatype is int

        # Another valid type
        datatype = model_with_datatypes._get_component_datatype(("Battery", "Specifications", "AnotherValidType"))
        assert datatype is str

        # Invalid type - string
        datatype = model_with_datatypes._get_component_datatype(("Battery", "Specifications", "InvalidType"))
        assert datatype is None

        # Invalid type - number
        datatype = model_with_datatypes._get_component_datatype(("Battery", "Specifications", "NonCallable"))
        assert datatype is None

    def test_safe_cast_value_successful_casts(self, basic_model) -> None:
        """
        Test _safe_cast_value with successful type conversions.

        GIVEN: Values that can be cast to target types
        WHEN: Attempting to cast values
        THEN: Should return correctly typed values
        """
        path = ("Battery", "Specifications", "Capacity mAh")

        # Int casting
        result = basic_model._safe_cast_value("1500", int, path)
        assert result == 1500
        assert isinstance(result, int)

        # Float casting
        result = basic_model._safe_cast_value("12.5", float, path)
        assert result == 12.5
        assert isinstance(result, float)

        # String casting
        result = basic_model._safe_cast_value(42, str, path)
        assert result == "42"
        assert isinstance(result, str)

        # Value already correct type
        result = basic_model._safe_cast_value(1000, int, path)
        assert result == 1000
        assert isinstance(result, int)

    def test_safe_cast_value_none_handling(self, model_with_datatypes) -> None:
        """
        Test _safe_cast_value None value handling for different types.

        GIVEN: None values with various target types
        WHEN: Attempting to cast None
        THEN: Should return type-appropriate defaults
        """
        path = ("Battery", "Specifications", "Test")

        # None to str
        result = model_with_datatypes._safe_cast_value(None, str, path)
        assert result == ""

        # None to int
        result = model_with_datatypes._safe_cast_value(None, int, path)
        assert result == 0

        # None to float
        result = model_with_datatypes._safe_cast_value(None, float, path)
        assert result == 0.0

        # None to bool
        result = model_with_datatypes._safe_cast_value(None, bool, path)
        assert result is False

        # None to list
        result = model_with_datatypes._safe_cast_value(None, list, path)
        assert result == []

    def test_safe_cast_value_none_handling_edge_cases(self, model_with_datatypes) -> None:
        """
        Test _safe_cast_value None handling for edge cases.

        GIVEN: None values with unusual target types
        WHEN: Attempting to cast None
        THEN: Should handle gracefully
        """
        path = ("Battery", "Specifications", "Test")

        # None to dict
        result = model_with_datatypes._safe_cast_value(None, dict, path)
        assert result == {}

        # None with unknown datatype
        class CustomType:  # pylint: disable=too-few-public-methods
            """Dummy class for testing."""

        result = model_with_datatypes._safe_cast_value(None, CustomType, path)
        assert result == ""

    def test_safe_cast_value_failed_casts(self, basic_model) -> None:
        """
        Test _safe_cast_value fallback when casting fails.

        GIVEN: Values that cannot be cast to target type
        WHEN: Attempting to cast
        THEN: Should fall back to _process_value
        """
        path = ("Battery", "Specifications", "Capacity mAh")

        # Failed int cast
        result = basic_model._safe_cast_value("not_a_number", int, path)
        assert result == "not_a_number"
        assert isinstance(result, str)

        # Dict/list types preserved
        result = basic_model._safe_cast_value({"key": "value"}, dict, path)
        assert result == {"key": "value"}
        assert isinstance(result, dict)

    def test_safe_cast_value_list_dict_special_handling(self, model_with_datatypes, caplog) -> None:
        """
        Test _safe_cast_value special handling for list/dict datatypes.

        GIVEN: Values with list or dict as target type
        WHEN: Attempting to cast
        THEN: Should log error and fall back to _process_value
        """
        path = ("Battery", "Specifications", "TestField")

        # List datatype
        result = model_with_datatypes._safe_cast_value("some_value", list, path)
        assert result == "some_value"
        assert "Failed to cast value" in caplog.text

        caplog.clear()

        # Dict datatype
        result = model_with_datatypes._safe_cast_value("another_value", dict, path)
        assert result == "another_value"
        assert "Failed to cast value" in caplog.text

    def test_safe_cast_value_attribute_error_handling(self, model_with_datatypes, caplog) -> None:
        """
        Test _safe_cast_value AttributeError handling.

        GIVEN: A datatype that raises AttributeError when called
        WHEN: Attempting to cast
        THEN: Should catch error and fall back to _process_value
        """
        path = ("Battery", "Specifications", "TestField")

        class AttributeErrorType(type):
            """Mock type that raises AttributeError."""

            def __call__(cls, *args, **kwargs) -> None:
                msg = "Mock AttributeError"
                raise AttributeError(msg)

        class MockDatatype(metaclass=AttributeErrorType):  # pylint: disable=too-few-public-methods
            """Dummy class for testing."""

        result = model_with_datatypes._safe_cast_value("test_value", MockDatatype, path)

        assert "Failed to cast value" in caplog.text
        assert "AttributeError" in caplog.text
        assert result == "test_value"

    def test_process_value_type_inference(self, basic_model) -> None:
        """
        Test _process_value automatic type inference and conversion.

        GIVEN: String values representing different data types
        WHEN: Processing values
        THEN: Should convert to appropriate types
        """
        # Integer conversion
        value = basic_model._process_value(("Battery", "Specifications", "Capacity mAh"), "2000")
        assert value == 2000
        assert isinstance(value, int)

        # Float conversion
        value = basic_model._process_value(("Frame", "Specifications", "Weight Kg"), "0.25")
        assert value == 0.25
        assert isinstance(value, float)

        # String handling with whitespace
        value = basic_model._process_value(("Battery", "Specifications", "Chemistry"), "  Lipo  ")
        assert value == "Lipo"
        assert isinstance(value, str)

        # Non-numeric string
        value = basic_model._process_value(("Flight Controller", "Notes"), "Special notes")
        assert value == "Special notes"
        assert isinstance(value, str)

    def test_process_value_version_field_special_handling(self, basic_model) -> None:
        """
        Test _process_value special handling for Version fields.

        GIVEN: Version field paths with various values
        WHEN: Processing values
        THEN: Values should remain as strings
        """
        # Version field should remain string
        value = basic_model._process_value(("Flight Controller", "Firmware", "Version"), "4.6.2")
        assert value == "4.6.2"
        assert isinstance(value, str)

        # Version field with numeric-looking value
        value = basic_model._process_value(("Test", "Version"), "42")
        assert value == "42"
        assert isinstance(value, str)

    def test_process_value_none_handling(self, model_with_datatypes) -> None:
        """
        Test _process_value None value handling.

        GIVEN: None values
        WHEN: Processing values
        THEN: Should convert to empty string
        """
        path = ("Battery", "Specifications", "TestField")
        result = model_with_datatypes._process_value(path, None)
        assert result == ""

        version_path = ("Battery", "Product", "Version")
        result = model_with_datatypes._process_value(version_path, None)
        assert result == ""

    def test_deep_merge_dicts_simple_merge(self, model_with_datatypes) -> None:
        """
        Test _deep_merge_dicts with simple dictionary merging.

        GIVEN: Two simple dictionaries
        WHEN: Merging them
        THEN: Should combine keys from both dictionaries
        """
        default = {"key1": "default1", "key2": "default2"}
        existing = {"key2": "existing2", "key3": "existing3"}

        result = model_with_datatypes._deep_merge_dicts(default, existing)

        assert result["key1"] == "default1"
        assert result["key2"] == "existing2"  # Existing overrides default
        assert result["key3"] == "existing3"

    def test_deep_merge_dicts_recursive_comprehensive(self, model_with_datatypes) -> None:
        """
        Test _deep_merge_dicts recursive merging with nested structures.

        GIVEN: Deeply nested dictionaries
        WHEN: Merging them recursively
        THEN: Should merge at all levels
        """
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
                    "level3": {"existing_value": "from_existing", "shared_key": "existing_shared"},
                    "existing_level2": "existing",
                },
                "simple_existing": "existing",
            },
            "top_level_existing": "existing",
        }

        result = model_with_datatypes._deep_merge_dicts(default, existing)

        # Verify deep recursive merging
        assert result["level1"]["level2"]["level3"]["default_value"] == "from_default"
        assert result["level1"]["level2"]["level3"]["existing_value"] == "from_existing"
        assert result["level1"]["level2"]["level3"]["shared_key"] == "existing_shared"
        assert result["level1"]["level2"]["default_level2"] == "default"
        assert result["level1"]["level2"]["existing_level2"] == "existing"
        assert result["level1"]["simple_default"] == "default"
        assert result["level1"]["simple_existing"] == "existing"
        assert result["top_level_default"] == "default"
        assert result["top_level_existing"] == "existing"

    def test_deep_merge_dicts_non_dict_existing_value(self, model_with_datatypes) -> None:
        """
        Test _deep_merge_dicts when existing value is not a dict.

        GIVEN: Default dict with nested dict, existing value as non-dict
        WHEN: Merging them
        THEN: Existing value should be preserved
        """
        default_with_dict = {"mixed_key": {"nested": "should_not_appear"}}
        existing_with_string = {"mixed_key": "string_value"}

        result = model_with_datatypes._deep_merge_dicts(default_with_dict, existing_with_string)

        assert result["mixed_key"] == "string_value"
        assert not isinstance(result["mixed_key"], dict)

    def test_reorder_components_basic_ordering(self) -> None:
        """
        Test _reorder_components basic component ordering.

        GIVEN: Components in random order
        WHEN: Reordering components
        THEN: Should follow defined order with unknowns at end
        """
        schema = VehicleComponentsJsonSchema({})
        model = ComponentDataModelBase({}, {}, schema)

        existing_components = {
            "RC Controller": {"Product": {"Manufacturer": "FrSky"}},
            "GNSS Receiver": {"Product": {"Manufacturer": "u-blox"}},
            "Battery": {"Product": {"Manufacturer": "Tattu"}},
            "Flight Controller": {"Product": {"Manufacturer": "Pixhawk"}},
            "Custom Sensor": {"Product": {"Manufacturer": "Custom"}},
        }

        result = model._reorder_components(existing_components)
        component_order = list(result.keys())

        # Known components should appear before unknown
        expected_known = ["Flight Controller", "Battery", "GNSS Receiver", "RC Controller"]
        for component in expected_known:
            if component in component_order:
                assert component_order.index(component) < component_order.index("Custom Sensor")

    def test_reorder_components_product_field_ordering(self) -> None:
        """
        Test _reorder_components Product field ordering.

        GIVEN: Component with Product fields in wrong order
        WHEN: Reordering components
        THEN: Product fields should be reordered with Version before URL
        """
        schema = VehicleComponentsJsonSchema({})
        model = ComponentDataModelBase({}, {}, schema)

        existing_components = {
            "Flight Controller": {
                "Product": {"Manufacturer": "Pixhawk", "URL": "https://pixhawk.org", "Model": "6C", "Version": "1.0"}
            }
        }

        result = model._reorder_components(existing_components)
        product_fields = list(result["Flight Controller"]["Product"].keys())

        version_index = product_fields.index("Version")
        url_index = product_fields.index("URL")
        assert version_index < url_index

    def test_data_structure_validation(self) -> None:
        """
        Test internal data structure validation.

        GIVEN: Various data structures
        WHEN: Creating model instances
        THEN: Should validate or initialize properly
        """
        schema = Mock(spec=VehicleComponentsJsonSchema)

        # Empty dict
        model = ComponentDataModelBase({}, {}, schema)
        assert model._data == {"Components": {}, "Format version": 1}

        # Valid structure
        valid_data = {"Components": {"Battery": {}}, "Format version": 1}
        model = ComponentDataModelBase(valid_data, {}, schema)
        assert "Components" in model._data
