#!/usr/bin/env python3

"""
Vehicle components JSON schema tests.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any
from unittest.mock import patch

import pytest

from ardupilot_methodic_configurator.data_model_vehicle_components_json_schema import VehicleComponentsJsonSchema

# pylint: disable=protected-access


class TestVehicleComponentsJsonSchema:
    """Test Vehicle Components JSON Schema business logic and behavior."""

    # pylint: disable=duplicate-code
    @pytest.fixture
    def minimal_schema(self) -> dict[str, Any]:
        """Fixture providing a minimal realistic schema for testing."""
        return {
            "properties": {
                "Components": {
                    "properties": {
                        "Flight Controller": {
                            "description": "Flight controller component",
                            "x-is-optional": False,
                            "allOf": [
                                {
                                    "properties": {
                                        "Product": {
                                            "description": "Product information",
                                            "x-is-optional": True,
                                        },
                                        "Specifications": {
                                            "description": "Technical specifications",
                                            "properties": {
                                                "MCU Series": {
                                                    "description": "Microcontroller series",
                                                    "type": "string",
                                                    "x-is-optional": False,
                                                }
                                            },
                                        },
                                    }
                                }
                            ],
                        },
                        "Battery": {
                            "description": "Battery component",
                            "properties": {
                                "Specifications": {
                                    "properties": {
                                        "Capacity mAh": {"type": "integer"},
                                        "Chemistry": {"type": "string"},
                                        "Number of cells": {"type": "integer"},
                                        "Volt per cell max": {"type": "number"},
                                        "Enabled": {"type": "boolean"},
                                    }
                                }
                            },
                        },
                    }
                }
            },
            "definitions": {
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
                },
                "product": {
                    "properties": {
                        "Manufacturer": {
                            "description": "Component manufacturer",
                            "type": "string",
                            "x-is-optional": False,
                        },
                        "Model": {
                            "description": "Component model identifier",
                            "type": "string",
                            "x-is-optional": True,
                        },
                    }
                },
            },
        }

    @pytest.fixture
    def complex_schema(self) -> dict[str, Any]:
        """Fixture providing a complex schema with various data types for testing."""
        return {
            "properties": {
                "Components": {
                    "properties": {
                        "Frame": {
                            "properties": {
                                "Specifications": {
                                    "properties": {
                                        "TOW min Kg": {"type": "number"},
                                        "TOW max Kg": {"type": "number"},
                                        "Config": {"type": "object"},
                                        "Tags": {"type": "array"},
                                        "Notes": {"type": "string"},
                                        "Available": {"type": "boolean"},
                                        "Count": {"type": "integer"},
                                        "Unknown": {"type": "unknowntype"},
                                        "NoType": {"description": "Field without type"},
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

    @pytest.fixture
    def schema_with_references(self) -> dict[str, Any]:
        """Fixture providing a schema with $ref references for testing."""
        return {
            "properties": {
                "Components": {
                    "properties": {
                        "RC Controller": {
                            "description": "RC controller component",
                            "properties": {
                                "Firmware": {"$ref": "#/definitions/firmware"},
                                "Product": {"$ref": "#/definitions/product"},
                            },
                        },
                        "Motors": {
                            "properties": {
                                "Product": {"$ref": "#/definitions/product"},
                                "Config": {"properties": {"Advanced": {"$ref": "#/definitions/advancedConfig"}}},
                            }
                        },
                    }
                }
            },
            "definitions": {
                "firmware": {
                    "description": "Controller firmware info",
                    "x-is-optional": True,
                },
                "product": {
                    "description": "Product information",
                    "properties": {"Manufacturer": {"type": "string", "description": "Manufacturer name"}},
                },
                "advancedConfig": {
                    "description": "Advanced configuration options",
                    "properties": {"Feature": {"type": "boolean", "description": "Feature toggle"}},
                },
            },
        }

    # pylint: enable=duplicate-code

    @pytest.fixture
    def json_schema_instance(self, minimal_schema) -> VehicleComponentsJsonSchema:
        """Fixture providing a configured VehicleComponentsJsonSchema instance."""
        return VehicleComponentsJsonSchema(minimal_schema)

    def test_user_can_extract_all_value_datatypes_from_schema(self, json_schema_instance) -> None:
        """
        User can extract all value datatypes from the schema for validation.

        GIVEN: A schema with various component types and properties
        WHEN: The user requests all value datatypes
        THEN: They should receive a mapping of components to their Python types
        """
        # Act: Extract all datatypes from the schema
        result = json_schema_instance.get_all_value_datatypes()

        # Assert: Result contains expected component structure
        assert isinstance(result, dict)
        assert "Flight Controller" in result
        assert "Battery" in result

        # Assert: Flight Controller has expected nested structure
        fc_types = result["Flight Controller"]
        assert "Product" in fc_types
        assert "Specifications" in fc_types
        assert fc_types["Specifications"]["MCU Series"] is str

        # Assert: Battery has expected type mappings
        battery_specs = result["Battery"]["Specifications"]
        assert battery_specs["Capacity mAh"] is int
        assert battery_specs["Chemistry"] is str
        assert battery_specs["Number of cells"] is int
        assert battery_specs["Volt per cell max"] is float
        assert battery_specs["Enabled"] is bool

    def test_user_can_handle_complex_json_schema_types(self, complex_schema) -> None:
        """
        User can extract datatypes from complex schemas with various JSON types.

        GIVEN: A schema with all possible JSON Schema types
        WHEN: The user extracts datatypes
        THEN: They should receive correct Python type mappings for all supported types
        """
        # Arrange: Create instance with complex schema
        json_schema = VehicleComponentsJsonSchema(complex_schema)

        # Act: Extract datatypes from complex schema
        result = json_schema.get_all_value_datatypes()

        # Assert: All JSON Schema types are correctly mapped to Python types
        frame_specs = result["Frame"]["Specifications"]
        assert frame_specs["TOW min Kg"] is float
        assert frame_specs["TOW max Kg"] is float
        assert frame_specs["Config"] is dict
        assert frame_specs["Tags"] is list
        assert frame_specs["Notes"] is str
        assert frame_specs["Available"] is bool
        assert frame_specs["Count"] is int
        assert frame_specs["Unknown"] is str  # Unknown types default to str
        assert frame_specs["NoType"] == {}  # No type creates empty dict

    def test_user_can_handle_empty_or_invalid_schemas(self) -> None:
        """
        User receives empty result when working with invalid schemas.

        GIVEN: An empty or invalid schema
        WHEN: The user tries to extract datatypes
        THEN: They should receive an empty result without errors
        """
        # Test with empty schema
        json_schema = VehicleComponentsJsonSchema({})
        result = json_schema.get_all_value_datatypes()
        assert not result

        # Test with schema missing Components
        incomplete_schema = {"properties": {"Other": {}}}
        json_schema = VehicleComponentsJsonSchema(incomplete_schema)
        result = json_schema.get_all_value_datatypes()
        assert not result

    def test_user_can_resolve_schema_references(self, schema_with_references) -> None:
        """
        User can extract datatypes from schemas with $ref references.

        GIVEN: A schema with $ref references to definitions
        WHEN: The user extracts datatypes
        THEN: References should be resolved and types extracted correctly
        """
        # Arrange: Create instance with schema containing references
        json_schema = VehicleComponentsJsonSchema(schema_with_references)

        # Act: Extract datatypes with reference resolution
        result = json_schema.get_all_value_datatypes()

        # Assert: References are resolved correctly
        assert "RC Controller" in result
        assert "Motors" in result

        # Assert: Referenced RC Controller has proper structure
        rc_controller = result["RC Controller"]
        assert "Firmware" in rc_controller

        # Assert: Referenced product definition is resolved
        motors = result["Motors"]
        assert "Product" in motors
        assert "Config" in motors
        motors_product = motors["Product"]
        assert "Manufacturer" in motors_product
        assert motors_product["Manufacturer"] is str

        # Assert: Nested references are resolved
        motors_config = motors["Config"]
        assert "Advanced" in motors_config
        assert "Feature" in motors_config["Advanced"]
        assert motors_config["Advanced"]["Feature"] is bool

    def test_user_can_modify_mcu_series_optionality(self, json_schema_instance) -> None:
        """
        User can modify the MCU Series field optionality in the schema.

        GIVEN: A schema with MCU Series field
        WHEN: The user changes its optional status
        THEN: The schema should be updated with the correct x-is-optional value
        """
        # Act: Set MCU Series as optional
        json_schema_instance.modify_schema_for_mcu_series(is_optional=True)

        # Assert: MCU Series is marked as optional
        flight_controller_def = json_schema_instance.schema["definitions"]["flightController"]
        properties_item = flight_controller_def["allOf"][0]
        mcu_series_field = properties_item["properties"]["Specifications"]["properties"]["MCU Series"]
        assert mcu_series_field.get("x-is-optional", False), "MCU Series should be marked as optional"

        # Act: Set MCU Series as non-optional
        json_schema_instance.modify_schema_for_mcu_series(is_optional=False)

        # Assert: MCU Series is not marked as optional
        assert not mcu_series_field.get("x-is-optional", False), "MCU Series should not be marked as optional"

    def test_user_handles_mcu_modification_errors_gracefully(self) -> None:
        """
        User receives appropriate error handling when MCU modification fails.

        GIVEN: Invalid or incomplete schemas
        WHEN: The user tries to modify MCU Series optionality
        THEN: The operation should handle errors gracefully without crashing
        """
        # Test with empty schema
        json_schema = VehicleComponentsJsonSchema({})

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_json_schema.logging_error") as mock_log:
            json_schema.modify_schema_for_mcu_series(is_optional=True)
            mock_log.assert_called_once()

        # Test with incomplete schema structure
        incomplete_schema = {"definitions": {"flightController": {"allOf": [{"properties": {}}]}}}
        json_schema = VehicleComponentsJsonSchema(incomplete_schema)

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_json_schema.logging_error") as mock_log:
            json_schema.modify_schema_for_mcu_series(is_optional=True)
            mock_log.assert_called_once()

    def test_user_can_get_component_property_descriptions(self, minimal_schema) -> None:
        """
        User can retrieve property descriptions and optional status from schema.

        GIVEN: A schema with described properties
        WHEN: The user requests property descriptions using various paths
        THEN: They should receive correct descriptions and optional status
        """
        # Arrange: Create instance with described schema
        json_schema = VehicleComponentsJsonSchema(minimal_schema)

        # Act & Assert: Test top-level component description
        description, is_optional = json_schema.get_component_property_description(("Flight Controller",))
        assert description == "Flight controller component"
        assert not is_optional

        # Act & Assert: Test section field description
        description, is_optional = json_schema.get_component_property_description(("Flight Controller", "Product"))
        assert description == "Product information"
        assert is_optional

        # Act & Assert: Test product field description
        description, is_optional = json_schema.get_component_property_description(
            ("Flight Controller", "Product", "Manufacturer")
        )
        assert description == "Component manufacturer"
        assert not is_optional

        # Act & Assert: Test nested property description
        description, is_optional = json_schema.get_component_property_description(
            ("Flight Controller", "Specifications", "MCU Series")
        )
        assert description == "Microcontroller series"
        assert not is_optional

    def test_user_handles_invalid_property_paths_gracefully(self, json_schema_instance) -> None:
        """
        User receives empty results for invalid property paths.

        GIVEN: A valid schema
        WHEN: The user requests descriptions for non-existent paths
        THEN: They should receive empty descriptions without errors
        """
        # Test empty path
        description, is_optional = json_schema_instance.get_component_property_description(())
        assert description == ""
        assert not is_optional

        # Test non-existent component
        description, is_optional = json_schema_instance.get_component_property_description(("NonExistent",))
        assert description == ""
        assert not is_optional

        # Test non-existent nested property
        description, is_optional = json_schema_instance.get_component_property_description(
            ("Flight Controller", "NonExistent", "Field")
        )
        assert description == ""
        assert not is_optional

    def test_user_handles_schema_exceptions_gracefully(self) -> None:
        """
        User receives error handling when schema operations encounter exceptions.

        GIVEN: A corrupted or problematic schema
        WHEN: The user tries to get property descriptions
        THEN: Exceptions should be caught and logged appropriately
        """
        # Arrange: Create schema that will cause exceptions
        problematic_schema = {"properties": {"Components": None}}
        json_schema = VehicleComponentsJsonSchema(problematic_schema)

        # Act & Assert: Exception handling during property description retrieval
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_json_schema.logging_error") as mock_log:
            description, is_optional = json_schema.get_component_property_description(("Flight Controller",))

            # Assert: Error was logged and safe defaults returned
            assert description == ""
            assert not is_optional
            mock_log.assert_called_once()
            assert "Exception occurred in get_component_property_description" in str(mock_log.call_args)

    def test_user_can_resolve_complex_schema_references(self, schema_with_references) -> None:
        """
        User can work with schemas containing reference chains where supported.

        GIVEN: A schema with nested and chained references
        WHEN: The user requests property descriptions
        THEN: References should be resolved correctly where the implementation supports it
        """
        # Arrange: Create instance with complex reference schema
        json_schema = VehicleComponentsJsonSchema(schema_with_references)

        # Act & Assert: Test top-level component description (not a reference)
        description, is_optional = json_schema.get_component_property_description(("RC Controller",))
        assert description == "RC controller component"
        assert not is_optional

        # Act & Assert: Test deeply nested reference (this works through _traverse_nested_path)
        description, is_optional = json_schema.get_component_property_description(("Motors", "Config", "Advanced", "Feature"))
        assert description == "Feature toggle"

        # Test reference resolution method directly
        ref_result = json_schema._resolve_schema_reference({"$ref": "#/definitions/product"})
        assert "Manufacturer" in ref_result["properties"]
        assert ref_result["properties"]["Manufacturer"]["description"] == "Manufacturer name"

    def test_schema_reference_resolution_handles_missing_refs(self) -> None:
        """
        User receives appropriate handling when schema references are broken.

        GIVEN: A schema with broken or missing references
        WHEN: The user tries to resolve references
        THEN: The system should handle missing references gracefully
        """
        # Arrange: Schema with broken reference
        broken_ref_schema = {
            "properties": {"Components": {"properties": {"Broken": {"$ref": "#/definitions/nonexistent"}}}},
            "definitions": {},
        }

        json_schema = VehicleComponentsJsonSchema(broken_ref_schema)

        # Act: Try to resolve broken reference
        result = json_schema._resolve_schema_reference({"$ref": "#/definitions/nonexistent"})

        # Assert: Broken reference returns empty dict
        assert result == {}

    # ==================== EDGE CASE TESTS ====================

    def test_json_type_conversion_edge_cases(self, json_schema_instance) -> None:
        """
        User receives appropriate type conversions for edge cases.

        GIVEN: A schema with edge case JSON types
        WHEN: The user requests type conversions
        THEN: They should receive appropriate Python types or defaults
        """
        # Test direct type conversion method
        assert json_schema_instance._json_type_to_python_type("string") is str
        assert json_schema_instance._json_type_to_python_type("number") is float
        assert json_schema_instance._json_type_to_python_type("integer") is int
        assert json_schema_instance._json_type_to_python_type("boolean") is bool
        assert json_schema_instance._json_type_to_python_type("array") is list
        assert json_schema_instance._json_type_to_python_type("object") is dict
        assert json_schema_instance._json_type_to_python_type("null") is type(None)

        # Test unknown type defaults to str
        assert json_schema_instance._json_type_to_python_type("unknown") is str
        assert json_schema_instance._json_type_to_python_type("") is str

    def test_nested_path_traversal_edge_cases(self, json_schema_instance) -> None:
        """
        User can handle complex nested path traversal scenarios.

        GIVEN: A schema with various nested structures
        WHEN: The user traverses complex paths
        THEN: The system should handle all traversal scenarios gracefully
        """
        # Test direct properties check
        schema_obj = {"properties": {"test": {"description": "test desc"}}}
        found, result = json_schema_instance._check_direct_properties(schema_obj, "test")
        assert found
        assert result == {"description": "test desc"}

        # Test missing properties
        found, result = json_schema_instance._check_direct_properties(schema_obj, "missing")
        assert not found

        # Test allOf constructs
        allof_schema = {
            "allOf": [
                {"properties": {"test1": {"type": "string"}}},
                {"$ref": "#/definitions/test", "properties": {"test2": {"type": "integer"}}},
            ]
        }
        json_schema_instance.schema = {"definitions": {"test": {"properties": {"ref_prop": {"type": "boolean"}}}}}

        found, result = json_schema_instance._check_allof_constructs(allof_schema, "test1")
        assert found
        assert result == {"type": "string"}

    def test_schema_modification_with_debug_logging(self, json_schema_instance) -> None:
        """
        User receives debug information during schema modifications.

        GIVEN: A schema being modified
        WHEN: Debug logging is enabled
        THEN: Appropriate debug messages should be logged
        """
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_json_schema.logging_debug") as mock_debug:
            # Test successful modification
            json_schema_instance.modify_schema_for_mcu_series(is_optional=True)

            # Verify debug logging occurred
            mock_debug.assert_called()
            call_args = str(mock_debug.call_args)
            assert "Modified schema: MCU Series" in call_args

    def test_comprehensive_error_scenarios(self) -> None:
        """
        User receives comprehensive error handling across all error scenarios.

        GIVEN: Various error-inducing conditions
        WHEN: The user performs operations
        THEN: All errors should be handled gracefully with appropriate logging
        """
        # Test schema modification with exception in MCU field access
        # pylint: disable=duplicate-code
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
        # pylint: enable=duplicate-code

        json_schema = VehicleComponentsJsonSchema(problematic_schema)

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_json_schema.logging_error") as mock_log:
            json_schema.modify_schema_for_mcu_series(is_optional=True)
            mock_log.assert_called()

    def test_schema_initialization_and_attribute_access(self, minimal_schema) -> None:
        """
        User can properly initialize and access schema attributes.

        GIVEN: A schema dictionary
        WHEN: The user creates a VehicleComponentsJsonSchema instance
        THEN: The schema should be properly stored and accessible
        """
        # Test proper initialization
        json_schema = VehicleComponentsJsonSchema(minimal_schema)
        assert json_schema.schema is minimal_schema

        # Test that the schema reference is maintained
        assert json_schema.schema["properties"]["Components"] is not None
        assert "Flight Controller" in json_schema.schema["properties"]["Components"]["properties"]
