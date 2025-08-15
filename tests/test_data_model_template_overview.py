#!/usr/bin/env python3

"""
Tests for the data_model_template_overview.py file.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import unittest

from ardupilot_methodic_configurator.data_model_template_overview import TemplateOverview


class TestTemplateOverview(unittest.TestCase):  # pylint: disable=missing-class-docstring
    def setUp(self) -> None:
        # Define sample data to be used in tests
        self.sample_data = {
            "Flight Controller": {"Product": {"Manufacturer": "ArduPilot", "Model": "Pixhawk4"}},
            "Frame": {"Specifications": {"TOW max Kg": "5"}},
            # ... add other components as per your structure
        }

    def test_template_overview_initialization(self) -> None:
        # Initialize the TemplateOverview with sample data
        template_overview = TemplateOverview(self.sample_data)

        # Check if attributes are set correctly
        assert template_overview.fc_manufacturer == "ArduPilot"
        assert template_overview.fc_model == "Pixhawk4"
        assert template_overview.tow_max_kg == "5"
        # .. similarly test other attributes

    def test_template_overview_column_labels(self) -> None:
        # Check if the column labels match the required order
        # pylint: disable=duplicate-code
        expected_columns = (
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
        assert TemplateOverview.columns() == expected_columns

    def test_template_overview_attributes_method(self) -> None:
        # Initialize the TemplateOverview with the sample data
        template_overview = TemplateOverview(self.sample_data)

        # Fetch the instance attribute keys
        attribute_keys = template_overview.attributes()

        # Check if the attribute keys match the expected set of attributes
        expected_attributes = {
            "fc_manufacturer",
            "fc_model",
            "tow_max_kg",
            "prop_diameter_inches",
            "rc_protocol",
            "telemetry_model",
            "esc_protocol",
            "gnss_model",
            "gnss_connection",
        }
        assert expected_attributes == set(attribute_keys)


if __name__ == "__main__":
    unittest.main()
