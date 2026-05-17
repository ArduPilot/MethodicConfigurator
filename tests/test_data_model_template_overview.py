#!/usr/bin/env python3

"""
Tests for the data_model_template_overview.py file.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest

from ardupilot_methodic_configurator.data_model_template_overview import TemplateOverview

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

EXPECTED_ATTRIBUTE_ORDER = [
    "fc_manufacturer",
    "fc_model",
    "tow_max_kg",
    "prop_diameter_inches",
    "rc_protocol",
    "telemetry_model",
    "esc_protocol",
    "gnss_model",
    "gnss_connection",
]

# pylint: disable=duplicate-code
EXPECTED_COLUMNS = (
    "Template path",
    "FC\nManufacturer",
    "FC\nModel",
    "TOW Max\n[Kg]",
    "Prop Diameter\n[inches]",
    "RC\nProtocol",
    "Telemetry\nModel",
    "ESC\nProtocol",
    "GNSS\nModel",
    "GNSS\nConnection",
)
# pylint: enable=duplicate-code


@pytest.fixture
def full_vehicle_data() -> dict:
    """Fixture providing a complete vehicle component dict covering every TemplateOverview attribute."""
    return {
        "Flight Controller": {"Product": {"Manufacturer": "ArduPilot", "Model": "Pixhawk4"}},
        "Frame": {"Specifications": {"TOW max Kg": "5"}},
        "Propellers": {"Specifications": {"Diameter_inches": "10"}},
        "RC Receiver": {"FC Connection": {"Protocol": "SBUS"}},
        "Telemetry": {"Product": {"Model": "SiK"}},
        "ESC": {"FC->ESC Connection": {"Protocol": "DSHOT600"}},
        "GNSS Receiver": {"Product": {"Model": "Here3"}, "FC Connection": {"Type": "UART"}},
    }


# ---------------------------------------------------------------------------
# Attribute extraction — one isolated case per attribute
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("component_data", "attribute", "expected_value"),
    [
        ({"Flight Controller": {"Product": {"Manufacturer": "Holybro"}}}, "fc_manufacturer", "Holybro"),
        ({"Flight Controller": {"Product": {"Model": "Kakute H7"}}}, "fc_model", "Kakute H7"),
        ({"Frame": {"Specifications": {"TOW max Kg": "10"}}}, "tow_max_kg", "10"),
        ({"Propellers": {"Specifications": {"Diameter_inches": "12"}}}, "prop_diameter_inches", "12"),
        ({"RC Receiver": {"FC Connection": {"Protocol": "CRSF"}}}, "rc_protocol", "CRSF"),
        ({"Telemetry": {"Product": {"Model": "RFD900"}}}, "telemetry_model", "RFD900"),
        ({"ESC": {"FC->ESC Connection": {"Protocol": "DSHOT300"}}}, "esc_protocol", "DSHOT300"),
        ({"GNSS Receiver": {"Product": {"Model": "F9P"}}}, "gnss_model", "F9P"),
        ({"GNSS Receiver": {"FC Connection": {"Type": "CAN"}}}, "gnss_connection", "CAN"),
    ],
)
def test_template_overview_extracts_each_attribute_from_its_own_component_key(
    component_data: dict, attribute: str, expected_value: str
) -> None:
    """
    TemplateOverview reads each attribute from exactly the right nested key path.

    GIVEN: A dict containing data for only one component
    WHEN: A TemplateOverview is instantiated
    THEN: The corresponding attribute holds the supplied value; all others default to ''
    """
    overview = TemplateOverview(component_data)
    assert getattr(overview, attribute) == expected_value


def test_template_overview_defaults_all_attributes_to_empty_string_when_data_is_empty() -> None:
    """
    TemplateOverview defaults every attribute to an empty string when given an empty dict.

    GIVEN: An empty component data dict
    WHEN: A TemplateOverview is instantiated
    THEN: All nine attributes are empty strings
    """
    overview = TemplateOverview({})
    for attribute in EXPECTED_ATTRIBUTE_ORDER:
        assert getattr(overview, attribute) == "", f"Expected {attribute!r} to be '' for empty data"


# ---------------------------------------------------------------------------
# columns() contract
# ---------------------------------------------------------------------------


def test_columns_returns_a_tuple() -> None:
    """
    columns() returns a tuple, not a list, preserving immutability.

    GIVEN: The TemplateOverview class
    WHEN: columns() is called
    THEN: The return type is tuple
    """
    assert isinstance(TemplateOverview.columns(), tuple)


def test_columns_returns_expected_labels_in_order() -> None:
    """
    columns() returns the correct column headers in the required display order.

    GIVEN: The TemplateOverview class
    WHEN: columns() is called
    THEN: The returned tuple matches the expected column labels and ordering
    """
    assert TemplateOverview.columns() == EXPECTED_COLUMNS


def test_column_count_is_one_more_than_attribute_count() -> None:
    """
    The number of columns equals the number of instance attributes plus one (Template path).

    GIVEN: A TemplateOverview instance and its columns() definition
    WHEN: Both are inspected
    THEN: len(columns) == len(attributes) + 1
    """
    overview = TemplateOverview({})
    assert len(TemplateOverview.columns()) == len(overview.attributes()) + 1


# ---------------------------------------------------------------------------
# attributes() contract
# ---------------------------------------------------------------------------


def test_attributes_returns_a_list() -> None:
    """
    attributes() returns a list, not a tuple or set.

    GIVEN: A TemplateOverview instance
    WHEN: attributes() is called
    THEN: The return type is list
    """
    assert isinstance(TemplateOverview({}).attributes(), list)


def test_attributes_returns_exactly_the_expected_keys(full_vehicle_data: dict) -> None:  # pylint: disable=redefined-outer-name
    """
    attributes() exposes exactly the expected set of instance attribute keys.

    GIVEN: A TemplateOverview instantiated with full data
    WHEN: attributes() is called
    THEN: The returned keys match the full set of expected attribute names
    """
    assert set(TemplateOverview(full_vehicle_data).attributes()) == set(EXPECTED_ATTRIBUTE_ORDER)


def test_attributes_preserves_declaration_order() -> None:
    """
    attributes() preserves the declaration order of __init__, which drives GUI column order.

    GIVEN: A TemplateOverview instance
    WHEN: attributes() is called
    THEN: The keys appear in the same order as declared in __init__
    """
    assert TemplateOverview({}).attributes() == EXPECTED_ATTRIBUTE_ORDER
