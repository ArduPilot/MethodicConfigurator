#!/usr/bin/env python3

"""
Vehicle Components data model tests for ComponentDataModelDisplay.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

import pytest
from test_data_model_vehicle_components_common import ComponentDataModelFixtures

from ardupilot_methodic_configurator.data_model_vehicle_components_display import ComponentDataModelDisplay
from ardupilot_methodic_configurator.data_model_vehicle_components_json_schema import VehicleComponentsJsonSchema

# pylint: disable=redefined-outer-name


@pytest.fixture
def mock_schema() -> MagicMock:
    """Fixture providing a mock schema for display testing."""
    schema = MagicMock()

    # Default behavior: non-optional components
    schema.get_component_property_description.return_value = ("Test description", False)

    return schema


@pytest.fixture
def display_model(mock_schema) -> ComponentDataModelDisplay:
    """Fixture providing a ComponentDataModelDisplay instance for testing."""
    # Create minimal required dependencies
    initial_data = {"Components": {}, "Format version": 1}
    component_datatypes = {"Flight Controller": {"Product": {"Manufacturer": str}}}
    schema_dict = ComponentDataModelFixtures.create_simple_schema()
    schema = VehicleComponentsJsonSchema(schema_dict)

    # Create and configure the display model
    model = ComponentDataModelDisplay(initial_data, component_datatypes, schema)
    # Override with mock schema for easier testing
    model.schema = mock_schema
    return model


@pytest.fixture
def sample_component_data() -> dict:
    """Fixture providing realistic component data for testing."""
    return {
        "Flight Controller": {
            "Product": {"Manufacturer": "Holybro", "Model": "Pixhawk 6C"},
            "Specifications": {"Processor": "STM32H7", "MCU Series": "H7"},
        },
        "Frame": {"Product": {"Manufacturer": "Custom", "Model": "QuadX"}},
    }


@pytest.fixture
def optional_schema() -> MagicMock:
    """Fixture providing a schema where some components are optional."""
    schema = MagicMock()

    def mock_description(path) -> tuple[str, bool]:
        # Make certain paths optional
        if "MCU Series" in path or "Optional Field" in path:
            return ("Optional description", True)
        return ("Required description", False)

    schema.get_component_property_description.side_effect = mock_description
    return schema


class TestSimpleModeDisplay:
    """Test component display logic in simple complexity mode."""

    def test_user_sees_only_required_components_in_simple_mode(self, display_model) -> None:
        """
        User sees only components with required fields when in simple mode.

        GIVEN: A component with both required and optional fields
        WHEN: The user views components in simple mode
        THEN: Only components with at least one required field should be displayed
        """
        # Arrange: Component with mixed required/optional fields
        component_data = {"Required Field": "value", "Optional Field": "value"}

        # Mock schema to return different optional status
        def mock_description(path) -> tuple[str, bool]:
            if "Optional Field" in path:
                return ("Optional description", True)
            return ("Required description", False)

        display_model.schema.get_component_property_description.side_effect = mock_description
        display_model.get_all_components = MagicMock(return_value=["Test Component"])

        # Act: Check if component should display in simple mode
        result = display_model.should_display_in_simple_mode("Test Component", component_data, [], "simple")

        # Assert: Component is displayed because it has required fields
        assert result is True

    def test_user_does_not_see_optional_only_components_in_simple_mode(self, display_model) -> None:
        """
        User does not see components that only contain optional fields in simple mode.

        GIVEN: A component containing only optional fields
        WHEN: The user views components in simple mode
        THEN: The component should be hidden from display
        """
        # Arrange: Component with only optional fields
        component_data = {"Optional Field 1": "value1", "Optional Field 2": "value2"}

        # Mock schema to return all fields as optional
        display_model.schema.get_component_property_description.return_value = ("Optional description", True)
        display_model.get_all_components = MagicMock(return_value=["Optional Component"])

        # Act: Check if component should display in simple mode
        result = display_model.should_display_in_simple_mode("Optional Component", component_data, [], "simple")

        # Assert: Component is hidden because all fields are optional
        assert result is False

    def test_user_sees_all_components_in_normal_mode(self, display_model) -> None:
        """
        User sees all components regardless of optional status in normal mode.

        GIVEN: Components with various required/optional field combinations
        WHEN: The user views components in normal mode
        THEN: All components should be displayed
        """
        # Arrange: Component with only optional fields
        component_data = {"Optional Field 1": "value1", "Optional Field 2": "value2"}

        display_model.schema.get_component_property_description.return_value = ("Optional description", True)

        # Act: Check if component should display in normal mode
        result = display_model.should_display_in_simple_mode("Any Component", component_data, [], "normal")

        # Assert: Component is displayed in normal mode
        assert result is True

    def test_user_sees_nested_components_with_required_fields_in_simple_mode(self, display_model) -> None:
        """
        User sees nested components that contain required fields in simple mode.

        GIVEN: A nested component structure with some required fields
        WHEN: The user views components in simple mode
        THEN: Parent components should be displayed if they contain any required nested fields
        """
        # Arrange: Nested component with required field deep inside
        nested_component = {"Nested Level": {"Required Field": "value"}}

        def mock_description(path) -> tuple[str, bool]:
            if "Required Field" in path:
                return ("Required description", False)
            return ("Optional description", True)

        display_model.schema.get_component_property_description.side_effect = mock_description
        display_model.get_all_components = MagicMock(return_value=["Parent Component"])

        # Act: Check if parent component should display
        result = display_model.should_display_in_simple_mode("Parent Component", nested_component, [], "simple")

        # Assert: Parent component is displayed because it contains required nested fields
        assert result is True


class TestLeafComponentDisplay:
    """Test leaf component display logic."""

    def test_user_sees_required_leaf_components_in_simple_mode(self, display_model) -> None:
        """
        User sees required leaf components in simple mode.

        GIVEN: A required leaf component
        WHEN: The user views components in simple mode
        THEN: The leaf component should be displayed
        """
        # Arrange: Required leaf component
        path = ("Flight Controller", "Product", "Manufacturer")
        display_model.schema.get_component_property_description.return_value = ("Required field", False)

        # Act: Check if leaf should display in simple mode
        result = display_model.should_display_leaf_in_simple_mode(path, "simple")

        # Assert: Required leaf is displayed
        assert result is True

    def test_user_does_not_see_optional_leaf_components_in_simple_mode(self, display_model) -> None:
        """
        User does not see optional leaf components in simple mode.

        GIVEN: An optional leaf component
        WHEN: The user views components in simple mode
        THEN: The leaf component should be hidden
        """
        # Arrange: Optional leaf component
        path = ("Flight Controller", "Specifications", "MCU Series")
        display_model.schema.get_component_property_description.return_value = ("Optional field", True)

        # Act: Check if leaf should display in simple mode
        result = display_model.should_display_leaf_in_simple_mode(path, "simple")

        # Assert: Optional leaf is hidden
        assert result is False

    def test_user_sees_all_leaf_components_in_normal_mode(self, display_model) -> None:
        """
        User sees all leaf components in normal mode regardless of optional status.

        GIVEN: Both required and optional leaf components
        WHEN: The user views components in normal mode
        THEN: All leaf components should be displayed
        """
        # Arrange: Optional leaf component
        path = ("Flight Controller", "Specifications", "MCU Series")
        display_model.schema.get_component_property_description.return_value = ("Optional field", True)

        # Act: Check if leaf should display in normal mode
        result = display_model.should_display_leaf_in_simple_mode(path, "normal")

        # Assert: All leaves are displayed in normal mode
        assert result is True


class TestWidgetConfigurationPreparation:
    """Test widget configuration preparation for UI components."""

    def test_system_prepares_correct_non_leaf_widget_config(self, display_model) -> None:
        """
        System prepares correct configuration for non-leaf widgets.

        GIVEN: A non-leaf component with description and optional status
        WHEN: The system prepares widget configuration
        THEN: All necessary configuration data should be included
        """
        # Arrange: Non-leaf component data
        key = "Flight Controller"
        value = {"Product": {"Manufacturer": "Holybro"}}
        path = []
        display_model.schema.get_component_property_description.return_value = ("Flight controller description", False)

        # Act: Prepare widget configuration
        config = display_model.prepare_non_leaf_widget_config(key, value, path)

        # Assert: Configuration contains all required fields
        assert config["key"] == "Flight Controller"
        assert config["value"] == value
        assert config["path"] == ("Flight Controller",)
        assert config["description"] == "Flight controller description"
        assert config["is_optional"] is False
        assert config["is_toplevel"] is True

    def test_system_prepares_correct_leaf_widget_config(self, display_model) -> None:
        """
        System prepares correct configuration for leaf widgets.

        GIVEN: A leaf component with description and optional status
        WHEN: The system prepares widget configuration
        THEN: All necessary configuration data should be included
        """
        # Arrange: Leaf component data
        key = "Manufacturer"
        value = "Holybro"
        path = ["Flight Controller", "Product"]
        display_model.schema.get_component_property_description.return_value = ("Manufacturer description", False)

        # Act: Prepare widget configuration
        config = display_model.prepare_leaf_widget_config(key, value, path)

        # Assert: Configuration contains all required fields
        assert config["key"] == "Manufacturer"
        assert config["value"] == "Holybro"
        assert config["path"] == ("Flight Controller", "Product", "Manufacturer")
        assert config["description"] == "Manufacturer description"
        assert config["is_optional"] is False

    def test_system_enhances_optional_component_descriptions(self, display_model) -> None:
        """
        System enhances descriptions for optional components with helpful text.

        GIVEN: An optional component with a description
        WHEN: The system prepares widget configuration
        THEN: The description should be enhanced with optional field guidance
        """
        # Arrange: Optional component with description
        key = "MCU Series"
        value = "H7"
        path = ["Flight Controller", "Specifications"]
        display_model.schema.get_component_property_description.return_value = ("MCU series description", True)

        # Act: Prepare widget configuration
        config = display_model.prepare_leaf_widget_config(key, value, path)

        # Assert: Description is enhanced for optional field
        assert "MCU series description" in config["description"]
        assert "optional" in config["description"].lower()
        assert config["is_optional"] is True

    def test_system_handles_empty_descriptions_gracefully(self, display_model) -> None:
        """
        System handles components with empty descriptions gracefully.

        GIVEN: A component with no description
        WHEN: The system prepares widget configuration
        THEN: An empty description should be provided without errors
        """
        # Arrange: Component with no description
        key = "Unknown Field"
        value = "value"
        path = ["Component"]
        display_model.schema.get_component_property_description.return_value = ("", False)

        # Act: Prepare widget configuration
        config = display_model.prepare_leaf_widget_config(key, value, path)

        # Assert: Empty description handled gracefully
        assert config["description"] == ""
        assert config["is_optional"] is False

    def test_system_identifies_toplevel_components_correctly(self, display_model) -> None:
        """
        System correctly identifies top-level components.

        GIVEN: Components at different nesting levels
        WHEN: The system prepares widget configuration
        THEN: Top-level status should be correctly identified
        """
        # Arrange: Top-level component
        display_model.schema.get_component_property_description.return_value = ("Description", False)

        # Act: Check top-level component
        toplevel_config = display_model.prepare_non_leaf_widget_config("Flight Controller", {}, [])

        # Act: Check nested component
        nested_config = display_model.prepare_non_leaf_widget_config("Product", {}, ["Flight Controller"])

        # Assert: Top-level status correctly identified
        assert toplevel_config["is_toplevel"] is True
        assert nested_config["is_toplevel"] is False


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling scenarios."""

    def test_system_handles_complex_nested_structures(self, display_model) -> None:
        """
        System handles deeply nested component structures correctly.

        GIVEN: A deeply nested component structure
        WHEN: The system evaluates display logic
        THEN: All levels should be processed correctly
        """
        # Arrange: Deeply nested structure
        deep_structure = {"Level1": {"Level2": {"Level3": {"Required Field": "value"}}}}

        def mock_description(path) -> tuple[str, bool]:
            if "Required Field" in path:
                return ("Required description", False)
            return ("Optional description", True)

        display_model.schema.get_component_property_description.side_effect = mock_description
        display_model.get_all_components = MagicMock(return_value=["Deep Component"])

        # Act: Check if deep structure should display
        result = display_model.should_display_in_simple_mode("Deep Component", deep_structure, [], "simple")

        # Assert: Deep structure is correctly evaluated
        assert result is True

    def test_system_handles_mixed_data_types_in_components(self, display_model) -> None:
        """
        System handles components with mixed data types correctly.

        GIVEN: Components containing different data types (strings, numbers, dicts)
        WHEN: The system evaluates display logic
        THEN: All data types should be processed correctly
        """
        # Arrange: Mixed data types
        mixed_component = {
            "string_field": "text_value",
            "number_field": 42,
            "float_field": 3.14,
            "nested_dict": {"inner_field": "inner_value"},
        }

        display_model.schema.get_component_property_description.return_value = ("Description", False)
        display_model.get_all_components = MagicMock(return_value=["Mixed Component"])

        # Act: Check if mixed component should display
        result = display_model.should_display_in_simple_mode("Mixed Component", mixed_component, [], "simple")

        # Assert: Mixed data types handled correctly
        assert result is True

    def test_system_handles_empty_components_gracefully(self, display_model) -> None:
        """
        System handles empty components without errors.

        GIVEN: An empty component structure
        WHEN: The system evaluates display logic
        THEN: No errors should occur and appropriate defaults should be returned
        """
        # Arrange: Empty component
        empty_component = {}
        display_model.get_all_components = MagicMock(return_value=["Empty Component"])

        # Act: Check if empty component should display
        result = display_model.should_display_in_simple_mode("Empty Component", empty_component, [], "simple")

        # Assert: Empty component handled gracefully
        assert result is False  # No fields to display


class TestUserWorkflows:
    """Test complete user workflows for component display."""

    def test_user_can_switch_between_complexity_modes(self, display_model, sample_component_data) -> None:
        """
        User can switch between simple and normal complexity modes with consistent behavior.

        GIVEN: A user viewing components in one complexity mode
        WHEN: They switch to a different complexity mode
        THEN: Component visibility should update appropriately
        """
        # Arrange: Component with optional fields
        component = sample_component_data["Flight Controller"]

        def mock_description(path) -> tuple[str, bool]:
            if "MCU Series" in path:
                return ("Optional field", True)
            return ("Required field", False)

        display_model.schema.get_component_property_description.side_effect = mock_description
        display_model.get_all_components = MagicMock(return_value=["Flight Controller"])

        # Act: Check display in both modes
        simple_mode_result = display_model.should_display_in_simple_mode("Flight Controller", component, [], "simple")
        normal_mode_result = display_model.should_display_in_simple_mode("Flight Controller", component, [], "normal")

        # Assert: Consistent behavior across mode switches
        assert simple_mode_result is True  # Has required fields
        assert normal_mode_result is True  # Always shows in normal mode

    def test_user_receives_appropriate_guidance_for_optional_fields(self, display_model) -> None:
        """
        User receives appropriate guidance when working with optional fields.

        GIVEN: A user configuring optional component fields
        WHEN: They view field descriptions
        THEN: Clear guidance about optional nature should be provided
        """
        # Arrange: Optional field configuration
        display_model.schema.get_component_property_description.return_value = ("This is an optional field", True)

        # Act: Prepare configuration for optional field
        config = display_model.prepare_leaf_widget_config("Optional Field", "value", ["Component"])

        # Assert: User receives clear optional field guidance
        assert "optional" in config["description"].lower()
        assert "blank" in config["description"].lower()
        assert config["is_optional"] is True

    def test_system_hides_components_with_only_optional_fields_in_simple_mode(self, display_model) -> None:
        """
        System correctly hides components that have only optional fields in simple mode.

        GIVEN: A component with only optional subcomponents
        WHEN: User is in simple mode
        THEN: The component should not be displayed (returns False)
        """
        # Arrange: Mock schema to return all fields as optional
        display_model.schema.get_component_property_description.return_value = ("Optional field", True)

        # Component with only optional fields
        component_data = {"OptionalField1": "value1", "OptionalField2": "value2"}

        # Act: Check if component should display in simple mode
        should_display = display_model.should_display_in_simple_mode(
            "TestComponent", component_data, ["TestComponent"], "simple"
        )

        # Assert: Component with only optional fields is hidden in simple mode
        assert should_display is False

    def test_system_enhances_optional_field_descriptions_when_description_exists(self, display_model) -> None:
        """
        System enhances description tooltips for optional fields when original description exists.

        GIVEN: An optional field with an existing description
        WHEN: User views field configuration
        THEN: The description should be enhanced with optional field guidance
        """
        # Arrange: Optional field with existing description
        display_model.schema.get_component_property_description.return_value = ("Existing description", True)

        # Act: Prepare widget config for optional field
        config = display_model.prepare_leaf_widget_config("optional_field", "value", ["Component"])

        # Assert: Description is enhanced with optional guidance
        description = config["description"]
        assert "Existing description" in description
        assert "optional" in description.lower()
        assert "blank" in description.lower()
        # Specifically test that the enhancement was applied
        assert "\n" in description  # The enhancement adds a newline
