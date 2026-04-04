#!/usr/bin/env python3

"""
Unit tests for low-level ComponentDataModelDisplay implementation details.

These tests verify internal methods and implementation details for coverage purposes.
For behavior-driven tests, see test_data_model_vehicle_components_display.py

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import MagicMock

import pytest
from test_data_model_vehicle_components_common import ComponentDataModelFixtures

from ardupilot_methodic_configurator.data_model_vehicle_components_display import ComponentDataModelDisplay

# pylint: disable=redefined-outer-name


@pytest.fixture
def mock_schema() -> MagicMock:
    """Fixture providing a mock schema for display testing."""
    return ComponentDataModelFixtures.create_mock_schema()


class TestDisplayUncoveredBranches:
    """Tests targeting previously uncovered branches in ComponentDataModelDisplay."""

    @pytest.fixture
    def display_model(self, mock_schema) -> ComponentDataModelDisplay:
        """Fixture providing a ComponentDataModelDisplay instance."""
        return ComponentDataModelFixtures.create_display_model_with_mock_schema(mock_schema)

    # ------------------------------------------------------------------
    # should_display_in_simple_mode - non-top-level dict with all-optional
    # ------------------------------------------------------------------
    def test_system_hides_non_toplevel_dict_when_all_subfields_are_optional(self, display_model) -> None:
        """
        should_display_in_simple_mode returns False for a non-top-level dict whose leaf fields are all marked optional.

        GIVEN: A call where path is non-empty (not top-level) and the value
               is a dict with leaf fields that are all optional
        WHEN: should_display_in_simple_mode is called in 'simple' mode
        THEN: False should be returned
        """
        # All fields optional → schema always returns (description, True)
        display_model.schema.get_component_property_description.return_value = ("desc", True)

        value = {"Field1": "value1", "Field2": "value2"}

        result = display_model.should_display_in_simple_mode("Specifications", value, ["Flight Controller"], "simple")

        assert result is False

    def test_system_shows_non_toplevel_dict_when_at_least_one_field_is_required(self, display_model) -> None:
        """
        should_display_in_simple_mode returns True for a non-top-level dict that has at least one non-optional leaf.

        GIVEN: A non-top-level dict where one leaf field is NOT optional
        WHEN: should_display_in_simple_mode is called in 'simple' mode
        THEN: True should be returned
        """
        # First call returns optional=False (required field found)
        display_model.schema.get_component_property_description.return_value = ("desc", False)

        value = {"RequiredField": "value1"}

        result = display_model.should_display_in_simple_mode("Specifications", value, ["Flight Controller"], "simple")

        assert result is True

    def test_system_recurses_into_nested_dicts_in_non_toplevel_path(self, display_model) -> None:
        """
        should_display_in_simple_mode recursively checks nested dicts for required fields.

        GIVEN: A non-top-level dict value that contains a nested dict, and the
               nested dict has a required leaf field
        WHEN: should_display_in_simple_mode is called in 'simple' mode
        THEN: True should be returned because the nested dict has a required field
        """
        # Make the nested leaf field required (not optional)
        display_model.schema.get_component_property_description.return_value = ("desc", False)

        # value = {"NestedSection": {"LeafField": "value"}} — nested dict structure
        nested_value = {"LeafField": "value"}
        value = {"NestedSection": nested_value}

        result = display_model.should_display_in_simple_mode("FCConnection", value, ["RC Receiver"], "simple")

        assert result is True

    # ------------------------------------------------------------------
    # prepare_non_leaf_widget_config - optional field with description (line 122)
    # ------------------------------------------------------------------
    def test_system_appends_optional_hint_to_non_leaf_description(self, display_model) -> None:
        """
        prepare_non_leaf_widget_config appends the optional hint to the description for optional keys.

        GIVEN: An optional component key with a non-empty description
        WHEN: prepare_non_leaf_widget_config is called
        THEN: The returned description should include the optional hint on a new line
        """
        display_model.schema.get_component_property_description.return_value = ("Section info", True)

        config = display_model.prepare_non_leaf_widget_config("Product", {"Manufacturer": "Test"}, ["Flight Controller"])

        assert "Section info" in config["description"]
        assert "optional" in config["description"].lower()
        assert "\n" in config["description"]
        assert "blank" in config["description"].lower()

    # ------------------------------------------------------------------
    # should_display_in_simple_mode - branch 57->54: top-level loop continues
    # after recursive call returns False
    # ------------------------------------------------------------------
    def test_system_continues_toplevel_loop_when_recursive_sub_section_returns_false(self, display_model) -> None:
        """
        Top-level loop continues when a recursive sub-section call returns False.

        GIVEN: A top-level component with two dict sub-sections, all leaf fields optional
        WHEN: should_display_in_simple_mode is called in 'simple' mode
        THEN: The first False recursive result causes loop continuation (not break),
              and the overall result is False
        """
        # All leaf fields are optional → recursive calls return False
        display_model.schema.get_component_property_description.return_value = ("desc", True)
        display_model.get_all_components = MagicMock(return_value=["TopComp"])

        # Two dict sub-sections: for loop must continue past first False recursive result
        value = {"Section1": {"leaf1": "v1"}, "Section2": {"leaf2": "v2"}}

        result = display_model.should_display_in_simple_mode("TopComp", value, [], "simple")

        assert result is False

    # ------------------------------------------------------------------
    # should_display_in_simple_mode - branch 70->82: non-top-level value is not a dict
    # ------------------------------------------------------------------
    def test_system_returns_false_when_non_toplevel_value_is_not_a_dict(self, display_model) -> None:
        """
        Non-top-level call returns False immediately when value is not a dict.

        GIVEN: A call with a non-empty path and a plain string as the value (not a dict)
        WHEN: should_display_in_simple_mode is called in 'simple' mode
        THEN: isinstance check fails, skipping the for-loop, and False is returned
        """
        result = display_model.should_display_in_simple_mode("leaf_key", "a_string_value", ["parent"], "simple")

        assert result is False

    # ------------------------------------------------------------------
    # should_display_in_simple_mode - branch 75->72: non-top-level loop continues
    # after recursive sub-dict call returns False
    # ------------------------------------------------------------------
    def test_system_continues_non_toplevel_loop_when_nested_recursive_call_returns_false(self, display_model) -> None:
        """
        Non-top-level loop continues when a nested recursive dict call returns False.

        GIVEN: A non-top-level component with two nested dict sub-sections, all leaves optional
        WHEN: should_display_in_simple_mode is called in 'simple' mode
        THEN: The first False recursive result causes loop continuation (not early return),
              and the overall result is False
        """
        # All leaf fields are optional → recursive calls return False
        display_model.schema.get_component_property_description.return_value = ("desc", True)

        # Two dict sub-sections in a non-top-level path: loop must continue past first False
        value = {"SubSection1": {"leaf1": "v1"}, "SubSection2": {"leaf2": "v2"}}

        result = display_model.should_display_in_simple_mode("Connection", value, ["Flight Controller"], "simple")

        assert result is False
