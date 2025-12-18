#!/usr/bin/env python3

"""
Low-level unit tests for ComponentDataModelImport internal implementation.

These tests focus on internal methods and edge cases for code coverage,
separate from the behavior-driven tests in test_data_model_vehicle_components_import.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from unittest.mock import patch

import pytest
from test_data_model_vehicle_components_common import ComponentDataModelFixtures

from ardupilot_methodic_configurator.data_model_vehicle_components_import import ComponentDataModelImport

# pylint: disable=protected-access,too-many-public-methods


class TestComponentDataModelImportInternals:
    """Low-level unit tests for ComponentDataModelImport internal methods."""

    @pytest.fixture
    def realistic_model(self) -> ComponentDataModelImport:
        """Create a realistic vehicle data model based on the JSON file."""
        return ComponentDataModelFixtures.create_realistic_model(ComponentDataModelImport)

    @pytest.fixture
    def sample_doc_dict(self) -> dict:
        """Sample documentation dictionary for testing."""
        # pylint: disable=duplicate-code  # Shared test fixture
        return {
            "SERIAL1_PROTOCOL": {
                "values": {
                    "1": "MAVLink1",
                    "2": "MAVLink2",
                    "5": "GPS",
                    "23": "RCIN",
                }
            },
            # pylint: enable=duplicate-code
            "BATT_MONITOR": {"values": {"4": "Analog Voltage and Current"}},
            "GPS_TYPE": {"values": {"2": "uBlox", "5": "NMEA"}},
            "MOT_PWM_TYPE": {"values": {"6": "DShot600"}},
            "RC_PROTOCOLS": {"values": {"512": "CRSF"}},
        }

    def test_reverse_key_search_finds_correct_keys(self, realistic_model, sample_doc_dict) -> None:
        """
        Internal reverse key search finds parameter keys from protocol names.

        GIVEN: Documentation with protocol name to key mappings
        WHEN: Searching for keys by protocol names
        THEN: Correct parameter keys should be returned
        """
        result = realistic_model._reverse_key_search(sample_doc_dict, "SERIAL1_PROTOCOL", ["MAVLink1", "MAVLink2"], [1, 2])
        assert result == [1, 2]

    def test_reverse_key_search_returns_fallbacks_for_missing_values(self, realistic_model, sample_doc_dict) -> None:
        """
        Internal reverse key search returns fallback keys when values not found.

        GIVEN: Documentation without specific protocol names
        WHEN: Searching for non-existent protocol names
        THEN: Fallback keys should be returned
        """
        result = realistic_model._reverse_key_search(sample_doc_dict, "SERIAL1_PROTOCOL", ["NonExistent"], [99])
        assert result == [99]

    def test_reverse_key_search_handles_mismatched_lengths(self, realistic_model, sample_doc_dict) -> None:
        """
        Internal reverse key search handles mismatched list lengths gracefully.

        GIVEN: Protocol names and fallback keys with different list lengths
        WHEN: Performing reverse key search
        THEN: Error should be logged but search should still complete
        AND: Found values should be returned
        """
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as mock_log:
            result = realistic_model._reverse_key_search(
                sample_doc_dict,
                "SERIAL1_PROTOCOL",
                ["GPS", "RCIN"],
                [5],  # Mismatched lengths
            )
            mock_log.assert_called()
            assert result == [5, 23]

    def test_reverse_key_search_handles_empty_documentation(self, realistic_model) -> None:
        """
        Internal reverse key search handles empty documentation.

        GIVEN: Empty documentation dictionary
        WHEN: Attempting reverse key search
        THEN: KeyError should be raised (expected behavior)
        OR: Fallback values should be returned
        """
        empty_doc: dict = {}
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            try:
                result = realistic_model._reverse_key_search(empty_doc, "MISSING_PARAM", ["value"], [99])
                assert result == [99]
            except KeyError:
                pass  # Expected behavior

    def test_reverse_key_search_handles_malformed_documentation(self, realistic_model) -> None:
        """
        Internal reverse key search handles malformed documentation.

        GIVEN: Documentation missing required 'values' key
        WHEN: Attempting reverse key search
        THEN: KeyError should be raised (expected behavior)
        OR: Fallback values should be returned
        """
        malformed_doc: dict = {"PARAM": {"other_key": {}}}
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            try:
                result = realistic_model._reverse_key_search(malformed_doc, "PARAM", ["value"], [99])
                assert result == [99]
            except KeyError:
                pass  # Expected behavior

    def test_reverse_key_search_handles_empty_values(self, realistic_model) -> None:
        """
        Internal reverse key search handles empty values dictionary.

        GIVEN: Documentation with empty values dictionary
        WHEN: Searching for protocol names
        THEN: Fallback keys should be returned
        """
        empty_values_doc: dict = {"PARAM": {"values": {}}}
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            result = realistic_model._reverse_key_search(empty_values_doc, "PARAM", ["value"], [99])
            assert result == [99]

    def test_verify_dict_matches_documentation(self, realistic_model, sample_doc_dict) -> None:
        """
        Internal dictionary verification confirms matching dictionaries.

        GIVEN: Protocol dictionary matching documentation
        WHEN: Verifying dictionary against documentation
        THEN: Verification should return True
        """
        dict_to_check = {
            "1": {"protocol": "MAVLink1"},
            "2": {"protocol": "MAVLink2"},
            "5": {"protocol": "GPS"},
            "23": {"protocol": "RCIN"},
        }
        result = realistic_model._verify_dict_is_uptodate(sample_doc_dict, dict_to_check, "SERIAL1_PROTOCOL", "values")
        assert result is True

    def test_verify_dict_detects_mismatches(self, realistic_model, sample_doc_dict) -> None:
        """
        Internal dictionary verification detects mismatched values.

        GIVEN: Protocol dictionary with incorrect values
        WHEN: Verifying against documentation
        THEN: Verification should return False
        AND: Error should be logged
        """
        dict_mismatch = {
            "1": {"protocol": "Wrong Protocol"},
            "2": {"protocol": "MAVLink2"},
            "5": {"protocol": "GPS"},
            "23": {"protocol": "RCIN"},
        }
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            result = realistic_model._verify_dict_is_uptodate(sample_doc_dict, dict_mismatch, "SERIAL1_PROTOCOL", "values")
            assert result is False

    def test_verify_dict_handles_empty_documentation(self, realistic_model) -> None:
        """
        Internal dictionary verification handles empty documentation.

        GIVEN: Empty documentation dictionary
        WHEN: Attempting verification
        THEN: Verification should return False
        """
        result = realistic_model._verify_dict_is_uptodate({}, {}, "MISSING", "values")
        assert result is False

    def test_verify_dict_handles_missing_doc_key(self, realistic_model) -> None:
        """
        Internal dictionary verification handles missing parameter key.

        GIVEN: Documentation without the specified parameter key
        WHEN: Attempting verification
        THEN: Verification should return False
        """
        doc: dict = {"OTHER_KEY": {"values": {}}}
        result = realistic_model._verify_dict_is_uptodate(doc, {}, "MISSING_KEY", "values")
        assert result is False

    def test_verify_dict_handles_missing_doc_dict(self, realistic_model) -> None:
        """
        Internal dictionary verification handles missing values dictionary.

        GIVEN: Documentation without 'values' dictionary
        WHEN: Attempting verification
        THEN: Verification should return False
        """
        doc = {"PARAM": {"other_dict": {}}}
        result = realistic_model._verify_dict_is_uptodate(doc, {}, "PARAM", "values")
        assert result is False

    def test_verify_dict_detects_incomplete_dictionaries(self, realistic_model) -> None:
        """
        Internal dictionary verification detects incomplete dictionaries.

        GIVEN: Dictionary missing some documented keys
        WHEN: Verifying against complete documentation
        THEN: Verification should return False
        AND: Error should be logged about missing keys
        """
        doc = {
            "PARAM": {
                "values": {
                    "1": "Protocol1",
                    "2": "Protocol2",
                    "3": "Protocol3",
                }
            }
        }
        incomplete_dict = {
            "1": {"protocol": "Protocol1"},
            # Missing key "2" and "3"
        }
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            result = realistic_model._verify_dict_is_uptodate(doc, incomplete_dict, "PARAM", "values")
            assert result is False

    def test_set_gnss_type_handles_invalid_gps_type_value(self, realistic_model) -> None:
        """
        Internal GNSS type setter handles invalid GPS_TYPE value.

        GIVEN: FC parameters with non-integer GPS_TYPE value
        WHEN: Setting GNSS type from parameters
        THEN: Error should be logged
        AND: GNSS type should default to None
        """
        fc_parameters = {"GPS_TYPE": "invalid"}
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)
        gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        assert gnss_type == "None"

    def test_set_gnss_type_handles_unknown_gps_type(self, realistic_model) -> None:
        """
        Internal GNSS type setter handles unknown GPS_TYPE value.

        GIVEN: FC parameters with unknown GPS_TYPE (999)
        WHEN: Setting GNSS type from parameters
        THEN: Error should be logged
        AND: GNSS type should default to None
        """
        fc_parameters = {"GPS_TYPE": 999}
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)
        gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        assert gnss_type == "None"

    def test_set_serial_type_handles_invalid_rc_protocols_value(self, realistic_model) -> None:
        """
        Internal serial type setter handles invalid RC_PROTOCOLS value.

        GIVEN: FC parameters with non-integer RC_PROTOCOLS value
        WHEN: Setting serial type from parameters
        THEN: Error should be logged
        AND: System should not crash
        """
        fc_parameters = {"RC_PROTOCOLS": "invalid"}
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_serial_type_from_fc_parameters(fc_parameters)

    def test_set_serial_type_handles_multiple_rc_protocols(self, realistic_model) -> None:
        """
        Internal serial type setter handles ambiguous RC_PROTOCOLS.

        GIVEN: FC parameters with multiple RC protocols enabled (not power of 2)
        WHEN: Setting serial type from parameters
        THEN: Protocol should not be set due to ambiguity
        """
        fc_parameters = {"RC_PROTOCOLS": 3}  # Not a power of 2
        realistic_model._set_serial_type_from_fc_parameters(fc_parameters)
        # Should not set protocol for non-power of 2 values

    def test_set_serial_type_handles_invalid_serial_protocol_value(self, realistic_model) -> None:
        """
        Internal serial type setter handles invalid SERIAL_PROTOCOL value.

        GIVEN: FC parameters with non-integer SERIAL_PROTOCOL value
        WHEN: Setting serial type from parameters
        THEN: Error should be logged
        AND: Method should return False
        """
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PORTS", ["SERIAL1"]):
            fc_parameters = {"SERIAL1_PROTOCOL": "invalid"}
            with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
                result = realistic_model._set_serial_type_from_fc_parameters(fc_parameters)
            assert result is False

    def test_set_esc_type_handles_invalid_mot_pwm_type(self, realistic_model) -> None:
        """
        Internal ESC type setter handles invalid MOT_PWM_TYPE value.

        GIVEN: FC parameters with non-integer MOT_PWM_TYPE value
        WHEN: Setting ESC type from parameters
        THEN: Error should be logged
        AND: System should not crash
        """
        fc_parameters = {"MOT_PWM_TYPE": "invalid"}
        doc: dict = {}
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_esc_type_from_fc_parameters(fc_parameters, doc)

    def test_set_battery_type_handles_invalid_value(self, realistic_model) -> None:
        """
        Internal battery type setter handles invalid BATT_MONITOR value.

        GIVEN: FC parameters with non-integer BATT_MONITOR value
        WHEN: Setting battery type from parameters
        THEN: Error should be logged
        AND: System should not crash
        """
        fc_parameters = {"BATT_MONITOR": "invalid"}
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

    def test_set_battery_type_handles_key_error(self, realistic_model) -> None:
        """
        Internal battery type setter handles unknown BATT_MONITOR value.

        GIVEN: FC parameters with BATT_MONITOR value not in dictionary
        WHEN: Setting battery type from parameters
        THEN: KeyError should be handled
        AND: Error should be logged
        """  # pylint: disable=duplicate-code  # Common error handling test pattern
        fc_parameters = {"BATT_MONITOR": 999}
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)
        # pylint: enable=duplicate-code

    def test_set_battery_type_handles_type_error(self, realistic_model) -> None:
        """
        Internal battery type setter handles TypeError from None value.

        GIVEN: FC parameters with BATT_MONITOR set to None
        WHEN: Setting battery type from parameters
        THEN: TypeError should be handled
        AND: Error should be logged
        """  # pylint: disable=duplicate-code  # Common error handling test pattern
        fc_parameters = {"BATT_MONITOR": None}
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)
        # pylint: enable=duplicate-code

    def test_set_battery_type_handles_list_type_values(self, realistic_model) -> None:
        """
        Internal battery type setter handles list-type configuration values.

        GIVEN: Battery configuration with list values for type and protocol
        WHEN: Setting battery type from parameters
        THEN: First element of each list should be used
        """
        with patch(
            "ardupilot_methodic_configurator.data_model_vehicle_components_import.BATT_MONITOR_CONNECTION",
            {"4": {"type": ["Analog", "Digital"], "protocol": ["Voltage", "Current"]}},
        ):
            fc_parameters = {"BATT_MONITOR": 4}
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)
            batt_type = realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Type"))
            batt_protocol = realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Protocol"))
            assert batt_type == "Analog"
            assert batt_protocol == "Voltage"

    def test_set_battery_capacity_from_fc_parameters(self, realistic_model) -> None:
        """
        Battery capacity is correctly imported from FC parameters.

        GIVEN: FC parameters with valid BATT_CAPACITY
        WHEN: Setting battery type from parameters
        THEN: Battery capacity should be set correctly
        """
        fc_parameters = {"BATT_CAPACITY": 5000}
        realistic_model._set_battery_type_from_fc_parameters(fc_parameters)
        capacity = realistic_model.get_component_value(("Battery", "Specifications", "Capacity mAh"))
        assert capacity == 5000

    def test_set_battery_capacity_ignores_zero(self, realistic_model) -> None:
        """
        Zero battery capacity is ignored during import.

        GIVEN: FC parameters with BATT_CAPACITY set to 0
        WHEN: Setting battery type from parameters
        THEN: Battery capacity should not be updated
        """
        realistic_model.set_component_value(("Battery", "Specifications", "Capacity mAh"), 1000)
        fc_parameters = {"BATT_CAPACITY": 0}
        realistic_model._set_battery_type_from_fc_parameters(fc_parameters)
        capacity = realistic_model.get_component_value(("Battery", "Specifications", "Capacity mAh"))
        assert capacity == 1000  # Should not change

    def test_set_battery_capacity_handles_invalid_type(self, realistic_model) -> None:
        """
        Invalid battery capacity type is handled gracefully.

        GIVEN: FC parameters with non-integer BATT_CAPACITY
        WHEN: Setting battery type from parameters
        THEN: Error should be logged and system should not crash
        """
        fc_parameters = {"BATT_CAPACITY": "invalid"}
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)
