#!/usr/bin/env python3

"""
Unit tests for VehicleComponentsJsonSchema internal implementation.

These tests focus on low-level implementation details for coverage purposes.
For behavior-driven tests, see test_data_model_vehicle_components_json_schema.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any
from unittest.mock import patch

import pytest
from test_data_model_vehicle_components_common import make_fc_schema

from ardupilot_methodic_configurator.data_model_vehicle_components_json_schema import VehicleComponentsJsonSchema

# pylint: disable=protected-access,too-many-public-methods


class TestVehicleComponentsJsonSchemaInternals:
    """Unit tests for internal implementation of VehicleComponentsJsonSchema."""

    @pytest.fixture
    def minimal_schema(self) -> dict[str, Any]:
        """Fixture providing a minimal schema for internal testing."""
        return {  # pylint: disable=duplicate-code  # Minimal schema structure for tests
            "properties": {
                "Components": {
                    "properties": {
                        "Flight Controller": {
                            "description": "Flight controller component",
                            "properties": {
                                "Product": {"description": "Product information"},
                            },
                        }
                    }
                }
            },
            "definitions": {
                "product": {
                    "description": "Product information",
                    "properties": {"Manufacturer": {"type": "string", "description": "Manufacturer name"}},
                }
            },
        }

    @pytest.fixture
    def json_schema_instance(self, minimal_schema) -> VehicleComponentsJsonSchema:
        """Fixture providing a configured VehicleComponentsJsonSchema instance."""
        return VehicleComponentsJsonSchema(minimal_schema)

    def test_json_type_to_python_type_string(self, json_schema_instance) -> None:
        """
        Test internal type conversion for string type.

        GIVEN: A JSON schema type "string"
        WHEN: Converting to Python type
        THEN: Should return str type
        """
        assert json_schema_instance._json_type_to_python_type("string") is str

    def test_json_type_to_python_type_number(self, json_schema_instance) -> None:
        """
        Test internal type conversion for number type.

        GIVEN: A JSON schema type "number"
        WHEN: Converting to Python type
        THEN: Should return float type
        """
        assert json_schema_instance._json_type_to_python_type("number") is float

    def test_json_type_to_python_type_integer(self, json_schema_instance) -> None:
        """
        Test internal type conversion for integer type.

        GIVEN: A JSON schema type "integer"
        WHEN: Converting to Python type
        THEN: Should return int type
        """
        assert json_schema_instance._json_type_to_python_type("integer") is int

    def test_json_type_to_python_type_boolean(self, json_schema_instance) -> None:
        """
        Test internal type conversion for boolean type.

        GIVEN: A JSON schema type "boolean"
        WHEN: Converting to Python type
        THEN: Should return bool type
        """
        assert json_schema_instance._json_type_to_python_type("boolean") is bool

    def test_json_type_to_python_type_array(self, json_schema_instance) -> None:
        """
        Test internal type conversion for array type.

        GIVEN: A JSON schema type "array"
        WHEN: Converting to Python type
        THEN: Should return list type
        """
        assert json_schema_instance._json_type_to_python_type("array") is list

    def test_json_type_to_python_type_object(self, json_schema_instance) -> None:
        """
        Test internal type conversion for object type.

        GIVEN: A JSON schema type "object"
        WHEN: Converting to Python type
        THEN: Should return dict type
        """
        assert json_schema_instance._json_type_to_python_type("object") is dict

    def test_json_type_to_python_type_null(self, json_schema_instance) -> None:
        """
        Test internal type conversion for null type.

        GIVEN: A JSON schema type "null"
        WHEN: Converting to Python type
        THEN: Should return NoneType
        """
        assert json_schema_instance._json_type_to_python_type("null") is type(None)

    def test_json_type_to_python_type_unknown_defaults_to_str(self, json_schema_instance) -> None:
        """
        Test internal type conversion defaults to str for unknown types.

        GIVEN: An unknown JSON schema type
        WHEN: Converting to Python type
        THEN: Should return str as default
        """
        assert json_schema_instance._json_type_to_python_type("unknown") is str
        assert json_schema_instance._json_type_to_python_type("") is str

    def test_check_direct_properties_found(self, json_schema_instance) -> None:
        """
        Test internal property check when property exists.

        GIVEN: A schema object with direct properties
        WHEN: Checking for an existing property
        THEN: Should return True and the property schema
        """
        schema_obj = {"properties": {"test": {"description": "test desc"}}}
        found, result = json_schema_instance._check_direct_properties(schema_obj, "test")
        assert found
        assert result == {"description": "test desc"}

    def test_check_direct_properties_not_found(self, json_schema_instance) -> None:
        """
        Test internal property check when property doesn't exist.

        GIVEN: A schema object with direct properties
        WHEN: Checking for a non-existent property
        THEN: Should return False (found is False)
        """
        schema_obj = {"properties": {"test": {"description": "test desc"}}}
        found, _result = json_schema_instance._check_direct_properties(schema_obj, "missing")
        assert not found

    def test_check_allof_constructs_found(self, json_schema_instance) -> None:
        """
        Test internal allOf construct check when property exists.

        GIVEN: A schema with allOf constructs
        WHEN: Checking for a property in allOf
        THEN: Should return True and the property schema
        """
        json_schema_instance.schema = {"definitions": {"test": {"properties": {"ref_prop": {"type": "boolean"}}}}}

        allof_schema = {
            "allOf": [
                {"properties": {"test1": {"type": "string"}}},
                {"$ref": "#/definitions/test", "properties": {"test2": {"type": "integer"}}},
            ]
        }

        found, result = json_schema_instance._check_allof_constructs(allof_schema, "test1")
        assert found
        assert result == {"type": "string"}

    def test_resolve_schema_reference_success(self, json_schema_instance) -> None:
        """
        Test internal schema reference resolution when reference exists.

        GIVEN: A schema with definitions
        WHEN: Resolving a valid reference
        THEN: Should return the referenced schema object
        """
        ref_result = json_schema_instance._resolve_schema_reference({"$ref": "#/definitions/product"})
        assert "Manufacturer" in ref_result["properties"]
        assert ref_result["properties"]["Manufacturer"]["description"] == "Manufacturer name"

    def test_resolve_schema_reference_missing(self) -> None:
        """
        Test internal schema reference resolution when reference is missing.

        GIVEN: A schema with broken reference
        WHEN: Resolving a non-existent reference
        THEN: Should return empty dict
        """
        broken_ref_schema = {
            "properties": {"Components": {"properties": {"Broken": {"$ref": "#/definitions/nonexistent"}}}},
            "definitions": {},
        }

        json_schema = VehicleComponentsJsonSchema(broken_ref_schema)
        result = json_schema._resolve_schema_reference({"$ref": "#/definitions/nonexistent"})
        assert result == {}

    def test_get_section_field_description_with_allof_ref_not_found(self) -> None:
        """
        Test internal section field description when property not in allOf with ref.

        GIVEN: A schema with allOf containing references but without the target property
        WHEN: Getting section field description for missing property
        THEN: Should return empty description and False for optional
        """
        schema_allof_ref = {
            "definitions": {"emptyDef": {"properties": {"OtherField": {"type": "string"}}}},
            "properties": {"Components": {"properties": {"Test": {"allOf": [{"$ref": "#/definitions/emptyDef"}]}}}},
        }

        json_schema = VehicleComponentsJsonSchema(schema_allof_ref)
        # Navigate to Test component and look for non-existent section
        current = json_schema.schema["properties"]["Components"]["properties"]["Test"]
        description, is_optional = json_schema._get_section_field_description(current, "NonExistent")
        assert description == ""
        assert is_optional is False

    def test_check_allof_constructs_with_ref_property_not_found(self) -> None:
        """
        Test internal allOf checking when reference doesn't have the property.

        GIVEN: A schema with allOf containing a reference without the target property
        WHEN: Checking for a property that doesn't exist in the reference
        THEN: Should return False and original schema object
        """
        schema_with_empty_ref = {"definitions": {"empty": {"properties": {"DifferentField": {"type": "integer"}}}}}

        json_schema = VehicleComponentsJsonSchema(schema_with_empty_ref)

        test_obj = {"allOf": [{"$ref": "#/definitions/empty"}]}

        found, result = json_schema._check_allof_constructs(test_obj, "NonExistentField")
        assert found is False
        assert result == test_obj

    def test_check_allof_constructs_direct_properties_not_found(self) -> None:
        """
        Test internal allOf checking when property not in direct properties of allOf item.

        GIVEN: A schema with allOf items that have properties but not the target one
        WHEN: Checking for a property that doesn't exist
        THEN: Should return False and original schema object
        """
        json_schema = VehicleComponentsJsonSchema({})

        test_obj = {"allOf": [{"properties": {"Field1": {"type": "string"}}}]}

        found, result = json_schema._check_allof_constructs(test_obj, "Field2")
        assert found is False
        assert result == test_obj

    def test_check_references_with_ref_but_no_properties(self) -> None:
        """
        Test internal reference checking when reference exists but has no properties.

        GIVEN: A schema with a reference to a definition without properties
        WHEN: Checking for a property
        THEN: Should return False when property not found
        """
        schema_ref_no_props = {"definitions": {"noprops": {"type": "object"}}}

        json_schema = VehicleComponentsJsonSchema(schema_ref_no_props)

        test_obj = {"$ref": "#/definitions/noprops"}

        found, result = json_schema._check_references(test_obj, "AnyField")
        assert found is False
        assert result == test_obj

    def test_check_references_with_allof_in_ref(self) -> None:
        """
        Test internal reference checking when reference has allOf without target property.

        GIVEN: A schema where reference points to definition with allOf
        WHEN: Checking for a property not in the allOf items
        THEN: Should return False when property not found
        """
        schema_ref_allof = {"definitions": {"withAllOf": {"allOf": [{"properties": {"Field1": {"type": "string"}}}]}}}

        json_schema = VehicleComponentsJsonSchema(schema_ref_allof)

        test_obj = {"$ref": "#/definitions/withAllOf"}

        found, result = json_schema._check_references(test_obj, "Field2")
        assert found is False
        assert result == test_obj

    def test_check_references_with_allof_in_ref_found(self) -> None:
        """
        Test internal reference checking when property found in reference's allOf.

        GIVEN: A schema where reference points to definition with allOf containing target property
        WHEN: Checking for the property
        THEN: Should return True and the property schema
        """
        schema_ref_allof_found = {
            "definitions": {
                "withAllOf": {"allOf": [{"properties": {"TargetField": {"type": "boolean", "description": "Found in allOf"}}}]}
            }
        }

        json_schema = VehicleComponentsJsonSchema(schema_ref_allof_found)

        test_obj = {"$ref": "#/definitions/withAllOf"}

        found, result = json_schema._check_references(test_obj, "TargetField")
        assert found is True
        assert result["type"] == "boolean"
        assert result["description"] == "Found in allOf"

    def test_modify_schema_logs_debug_info(self) -> None:
        """
        Test internal debug logging during schema modification.

        GIVEN: A schema being modified with debug logging enabled
        WHEN: Modifying MCU Series optionality
        THEN: Appropriate debug messages should be logged
        """
        minimal_schema = {
            "properties": {
                "Components": {
                    "properties": {
                        "Flight Controller": {
                            "allOf": [
                                {
                                    "properties": {
                                        "Specifications": {
                                            "properties": {
                                                "MCU Series": {
                                                    "description": "Microcontroller series",
                                                    "type": "string",
                                                    "x-is-optional": False,
                                                }
                                            }
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
            },
            "definitions": {  # pylint: disable=duplicate-code  # Schema fixture for MCU tests
                "flightController": {
                    "allOf": [
                        {
                            "properties": {
                                "Specifications": {
                                    "properties": {
                                        "MCU Series": {
                                            "description": "Microcontroller series",
                                            "type": "string",
                                            "x-is-optional": False,
                                        }
                                    }
                                }
                            }
                        }
                    ]
                }
            },
            # pylint: enable=duplicate-code
        }

        json_schema = VehicleComponentsJsonSchema(minimal_schema)

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_json_schema.logging_debug") as mock_debug:
            # Test successful modification
            json_schema.modify_schema_for_mcu_series(is_optional=True)

            # Verify debug logging occurred
            mock_debug.assert_called()
            call_args = str(mock_debug.call_args)
            assert "Modified schema: MCU Series" in call_args

    def test_error_handling_in_schema_modification(self) -> None:
        """
        Test internal error handling during schema modification.

        GIVEN: Various error-inducing schema conditions
        WHEN: Performing schema modification operations
        THEN: Errors should be handled and logged appropriately
        """
        # Test schema modification with exception in MCU field access
        problematic_schema = {
            "definitions": {
                "flightController": {
                    "allOf": [
                        {
                            "properties": {
                                "Specifications": {
                                    "properties": {
                                        "MCU Series": None  # This will cause an exception
                                    }
                                }
                            }
                        }
                    ]
                }
            }
        }

        json_schema = VehicleComponentsJsonSchema(problematic_schema)

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_json_schema.logging_error") as mock_log:
            json_schema.modify_schema_for_mcu_series(is_optional=True)
            mock_log.assert_called()

    def test_modify_schema_logs_error_when_flight_controller_def_has_no_allof(self) -> None:
        """
        modify_schema_for_mcu_series logs an error when flightController definition has no allOf.

        GIVEN: A schema where definitions.flightController exists but contains no 'allOf' key
        WHEN: modify_schema_for_mcu_series is called
        THEN: The 'if allOf in flight_controller_def' check is False (arc 126->132),
              flight_controller_properties stays None, and an error is logged
        """
        schema_no_allof = {
            "definitions": {
                "flightController": {
                    "properties": {"Firmware": {"type": "string"}}  # no 'allOf' key
                }
            }
        }
        json_schema = VehicleComponentsJsonSchema(schema_no_allof)

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_json_schema.logging_error") as mock_err:
            json_schema.modify_schema_for_mcu_series(is_optional=True)

        mock_err.assert_called()

    def test_get_product_field_description_returns_empty_for_unknown_product_field(self) -> None:
        """
        _get_product_field_description returns ('', False) when field_name is not in product definition.

        GIVEN: A schema with definitions.product containing 'Manufacturer' only
        WHEN: get_component_property_description is called with a path like
              ('FC', 'Product', 'NonExistentField')
        THEN: ('', False) is returned (line 203 in _get_product_field_description)
        """
        schema = {
            "properties": {"Components": {"properties": {"Flight Controller": {"description": "FC"}}}},
            "definitions": {"product": {"properties": {"Manufacturer": {"type": "string"}}}},
        }
        json_schema = VehicleComponentsJsonSchema(schema)

        result = json_schema.get_component_property_description(("Flight Controller", "Product", "NonExistentField"))

        assert result == ("", False)

    def test_get_section_field_description_returns_direct_property_description(self) -> None:
        """
        _get_section_field_description returns description when section found in direct properties.

        GIVEN: A schema where 'Flight Controller' has 'Specifications' in its direct properties
        WHEN: get_component_property_description is called with path ('Flight Controller', 'Specifications')
        THEN: The description from the direct property is returned (line 240)
        """
        fc_body = {"description": "FC", "properties": {"Specifications": {"description": "Hardware specifications"}}}
        schema = make_fc_schema(fc_body)
        json_schema = VehicleComponentsJsonSchema(schema)

        result = json_schema.get_component_property_description(("Flight Controller", "Specifications"))

        assert result == ("Hardware specifications", False)

    def test_get_section_field_description_finds_section_via_ref_in_allof(self) -> None:
        """
        _get_section_field_description returns description when section found via $ref inside allOf.

        GIVEN: A schema where 'Flight Controller' has an allOf with a $ref, and the referenced
               definition contains the target section in its properties
        WHEN: get_component_property_description is called with path ('Flight Controller', 'Firmware')
        THEN: The description from the resolved reference is returned (line 250)
        """
        schema = {
            "properties": {"Components": {"properties": {"Flight Controller": {"allOf": [{"$ref": "#/definitions/fcBase"}]}}}},
            "definitions": {
                "fcBase": {"properties": {"Firmware": {"description": "Firmware section", "x-is-optional": True}}}
            },
        }
        json_schema = VehicleComponentsJsonSchema(schema)

        result = json_schema.get_component_property_description(("Flight Controller", "Firmware"))

        assert result == ("Firmware section", True)

    def test_modify_schema_logs_error_when_allof_has_no_specifications(self) -> None:
        """
        modify_schema_for_mcu_series logs an error when allOf items lack Specifications.

        GIVEN: A schema where flightController.allOf exists but no item contains 'Specifications'
        WHEN: modify_schema_for_mcu_series is called
        THEN: An error should be logged ('Could not find Specifications ...')
              and the function should return early without modifying anything
        """
        schema_no_specs = {
            "definitions": {"flightController": {"allOf": [{"properties": {"NotSpecifications": {"type": "string"}}}]}}
        }
        json_schema = VehicleComponentsJsonSchema(schema_no_specs)

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_json_schema.logging_error") as mock_err:
            json_schema.modify_schema_for_mcu_series(is_optional=True)

        mock_err.assert_called()

    def test_modify_schema_does_nothing_when_specifications_has_no_mcu_series_property(self) -> None:
        """
        modify_schema_for_mcu_series exits silently when MCU Series is absent from Specifications.

        GIVEN: A schema where flightController references Specifications, but Specifications
               has no 'properties' key (or no 'MCU Series' entry)
        WHEN: modify_schema_for_mcu_series is called
        THEN: No error should be logged and the function should complete without modification
        """
        schema_no_mcu = {
            "definitions": {
                "flightController": {
                    "allOf": [
                        {
                            "properties": {
                                "Specifications": {"type": "object"}  # no 'properties' sub-key
                            }
                        }
                    ]
                }
            }
        }
        json_schema = VehicleComponentsJsonSchema(schema_no_mcu)

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_json_schema.logging_error") as mock_err:
            json_schema.modify_schema_for_mcu_series(is_optional=True)

        mock_err.assert_not_called()

    def test_get_component_property_description_returns_empty_for_unknown_top_level_component(self) -> None:
        """
        get_component_property_description returns empty tuple for an unknown top-level component.

        GIVEN: A schema without 'NonExistentComponent' in its Components properties
        WHEN: get_component_property_description is called with a single-element path
        THEN: ('', False) should be returned
        """
        schema = {"properties": {"Components": {"properties": {"Flight Controller": {"description": "FC description"}}}}}
        json_schema = VehicleComponentsJsonSchema(schema)

        result = json_schema.get_component_property_description(("NonExistentComponent",))

        assert result == ("", False)

    def test_get_component_property_description_returns_empty_for_unknown_component_in_nested_path(self) -> None:
        """
        get_component_property_description returns empty tuple for unknown component in nested path.

        The top-level component is not found while resolving a multi-element path.

        GIVEN: A schema without 'NonExistent' as a component type
        WHEN: get_component_property_description is called with a path starting with 'NonExistent'
        THEN: ('', False) should be returned
        """
        schema = {"properties": {"Components": {"properties": {"Flight Controller": {"description": "FC description"}}}}}
        json_schema = VehicleComponentsJsonSchema(schema)

        result = json_schema.get_component_property_description(("NonExistent", "Specifications", "MCU Series"))

        assert result == ("", False)

    def test_get_component_property_description_returns_empty_for_missing_section(self) -> None:
        """
        get_component_property_description returns empty tuple for a missing section path.

        When len(path)==2 and the section is not in the component schema, ('', False) is returned.

        GIVEN: A schema with 'Flight Controller' in Components.properties
               but no 'NonExistentSection' anywhere
        WHEN: get_component_property_description is called with path of length 2
        THEN: ('', False) should be returned from _get_section_field_description
        """
        schema = {
            "properties": {
                "Components": {
                    "properties": {
                        "Flight Controller": {
                            "description": "FC",
                            "properties": {"Product": {"description": "Product info"}},
                        }
                    }
                }
            }
        }
        json_schema = VehicleComponentsJsonSchema(schema)

        result = json_schema.get_component_property_description(("Flight Controller", "NonExistentSection"))

        assert result == ("", False)

    def test_traverse_nested_path_returns_empty_when_part_not_found_in_any_strategy(self) -> None:
        """
        _traverse_nested_path returns ('', False) when a path part is not found.

        No lookup strategy (direct, allOf, or ref) locates the requested property.
        Also exercises: 243->257 (len(path)!=2 branch) and 289->302 (no allOf in schema_obj).

        GIVEN: A schema where 'Flight Controller' has only a 'Product' property
        WHEN: get_component_property_description is called with a length-3 path whose
              second element is 'Specifications' (which does not exist)
        THEN: _traverse_nested_path should exhaust all strategies and return ('', False)
        """
        schema = {
            "properties": {
                "Components": {
                    "properties": {
                        "Flight Controller": {
                            "description": "FC",
                            "properties": {"Product": {"description": "Product section"}},
                        }
                    }
                }
            }
        }
        json_schema = VehicleComponentsJsonSchema(schema)

        # path length 3 with path[1] != 'Product' -> goes to _traverse_nested_path
        result = json_schema.get_component_property_description(("Flight Controller", "Specifications", "Processor"))

        assert result == ("", False)

    def test_check_allof_constructs_finds_property_via_ref_inside_allof_item(self) -> None:
        """
        _check_allof_constructs returns True when the target property is found via $ref in allOf.

        The first allOf item lacks the property but the second resolves via $ref to a definition
        that contains it.

        GIVEN: An allOf schema where the first item doesn't have the property
               but the second item is a $ref that resolves to a definition containing it
        WHEN: _check_allof_constructs is called for the target property
        THEN: Should return True and the property schema
        """
        schema = {
            "definitions": {"myDef": {"properties": {"TargetProp": {"type": "string", "description": "Found via $ref"}}}}
        }
        json_schema = VehicleComponentsJsonSchema(schema)

        test_obj = {
            "allOf": [
                {"properties": {"OtherProp": {"type": "integer"}}},  # doesn't have TargetProp
                {"$ref": "#/definitions/myDef"},  # resolves to definition with TargetProp
            ]
        }

        found, result = json_schema._check_allof_constructs(test_obj, "TargetProp")

        assert found is True
        assert result["type"] == "string"

    def test_check_references_finds_property_in_direct_properties_of_referenced_definition(self) -> None:
        """
        _check_references returns True for a target property in referenced definition's properties.

        The $ref resolves to a definition with direct properties (not via allOf).

        GIVEN: A schema where the $ref resolves to a definition with direct properties
               containing the target property
        WHEN: _check_references is called for the target property
        THEN: Should return True and the property schema
        """
        schema = {
            "definitions": {
                "myDirectDef": {"properties": {"DirectProp": {"type": "boolean", "description": "Direct property"}}}
            }
        }
        json_schema = VehicleComponentsJsonSchema(schema)

        test_obj = {"$ref": "#/definitions/myDirectDef"}

        found, result = json_schema._check_references(test_obj, "DirectProp")

        assert found is True
        assert result["type"] == "boolean"
