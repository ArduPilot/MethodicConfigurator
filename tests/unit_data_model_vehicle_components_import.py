#!/usr/bin/env python3

"""
Low-level unit tests for ComponentDataModelImport internal implementation.

These tests focus on internal methods and edge cases for code coverage,
separate from the behavior-driven tests in test_data_model_vehicle_components_import.py.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# pylint: disable=duplicate-code  # Unit tests may have similar structure to integration tests

from unittest.mock import patch

import pytest
from test_data_model_vehicle_components_common import ComponentDataModelFixtures

import ardupilot_methodic_configurator.data_model_vehicle_components_import as _import_module
from ardupilot_methodic_configurator.battery_cell_voltages import BATTERY_DEFAULT_CHEMISTRY, BatteryCell
from ardupilot_methodic_configurator.data_model_vehicle_components_import import BatteryVoltageSpecs, ComponentDataModelImport
from ardupilot_methodic_configurator.data_model_vehicle_components_validation import ComponentDataModelValidation

# pylint: disable=protected-access,too-many-public-methods,too-many-lines


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
        with patch(
            "ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"
        ) as mock_log:
            result = realistic_model._reverse_key_search(sample_doc_dict, "SERIAL1_PROTOCOL", ["NonExistent"], [99])

        assert result == [99]
        mock_log.assert_called_once_with("No values found for %s in the metadata", "SERIAL1_PROTOCOL")

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
            mock_log.assert_called_once_with(
                "Length of values %u and fallbacks %u differ for %s", 2, 1, "SERIAL1_PROTOCOL"
            )
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

    @pytest.mark.parametrize(
        ("parameters", "voltage_type", "expected"),
        [
            ({}, "Volt per cell max", ""),
            ({"MOT_BAT_VOLT_MAX": 16.8}, "Volt per cell max", "MOT_BAT_VOLT_MAX"),
            ({"MOT_BAT_VOLT_MAX": 16.8, "Q_M_BAT_VOLT_MAX": 16.8}, "Volt per cell max", "Q_M_BAT_VOLT_MAX"),
            ({"MOT_BAT_VOLT_MIN": 12.0}, "Volt per cell min", "MOT_BAT_VOLT_MIN"),
        ],
    )
    def test_motor_battery_voltage_parameter_uses_priority_and_empty_string_fallback(
        self, parameters: dict[str, float], voltage_type: str, expected: str
    ) -> None:
        """The preferred motor voltage key is returned, with an empty string when none is present."""
        assert ComponentDataModelImport._get_motor_battery_voltage_parameter(parameters, voltage_type) == expected

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
        with patch(
            "ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning"
        ) as mock_warning:
            result = realistic_model._verify_dict_is_uptodate(sample_doc_dict, dict_mismatch, "SERIAL1_PROTOCOL", "values")
            assert result is False
        mock_warning.assert_called_once_with(
            "Protocol %s does not match %s in %s metadata", "Wrong Protocol", "MAVLink1", "SERIAL1_PROTOCOL"
        )

    def test_verify_dict_accepts_arduplane_47_ina2xx_label(self, realistic_model) -> None:
        """Accept the expanded INA2XX label introduced in ArduPilot 4.7.x metadata."""
        doc = {
            "BATT_MONITOR": {
                "values": {"21": "INA2XX (INA226 INA228 INA238 INA231 INA260)"},
            }
        }
        dict_to_check = {"21": {"protocol": "INA2XX"}}

        assert realistic_model._verify_dict_is_uptodate(doc, dict_to_check, "BATT_MONITOR", "values") is True

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
        with patch(
            "ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning"
        ) as mock_warning:
            result = realistic_model._verify_dict_is_uptodate(doc, incomplete_dict, "PARAM", "values")
            assert result is False
        assert [call.args for call in mock_warning.call_args_list] == [
            ("Protocol %s (%s) not found in %s code dictionary (firmware may be newer)", "Protocol2", "2", "PARAM"),
            ("Protocol %s (%s) not found in %s code dictionary (firmware may be newer)", "Protocol3", "3", "PARAM"),
        ]

    def test_verify_bitmask_protocols_expands_bit_positions_and_continues_after_invalid_keys(
        self, realistic_model
    ) -> None:
        """Bitmask metadata maps positions to powers of two and skips malformed positions."""
        doc = {"RC_PROTOCOLS": {"Bitmask": {"invalid": "Ignored", "0": "Unexpected", "2": "Third"}}}
        protocols = {"1": {"protocol": "First"}, "4": {"protocol": "Third"}}

        with patch(
            "ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning"
        ) as mock_warning:
            result = realistic_model._verify_dict_is_uptodate(doc, protocols, "RC_PROTOCOLS", "Bitmask")

        assert result is False
        assert [call.args for call in mock_warning.call_args_list] == [
            ("Invalid bit position %s in %s metadata", "invalid", "RC_PROTOCOLS"),
            ("Protocol %s does not match %s in %s metadata", "First", "Unexpected", "RC_PROTOCOLS"),
        ]

    def test_verify_protocol_rename_does_not_skip_later_mismatches(self, realistic_model) -> None:
        """A documented rename exception does not hide a mismatch later in the same metadata."""
        doc = {"PARAM": {"values": {"1": "MAV", "2": "Different"}}}
        protocols = {"1": {"protocol": "MAVLink"}, "2": {"protocol": "Expected"}}

        with patch(
            "ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning"
        ) as mock_warning:
            result = realistic_model._verify_dict_is_uptodate(doc, protocols, "PARAM", "values")

        assert result is False
        mock_warning.assert_called_once_with(
            "Protocol %s does not match %s in %s metadata", "Expected", "Different", "PARAM"
        )

    @pytest.mark.parametrize("param_name", ["GPS_TYPE", "GPS1_TYPE"])
    def test_set_gnss_type_handles_invalid_gps_type_value(self, realistic_model, param_name: str) -> None:  # type: ignore[misc]
        """
        Internal GNSS type setter handles invalid GPS_TYPE value.

        GIVEN: FC parameters with non-integer GPS_TYPE value
        WHEN: Setting GNSS type from parameters
        THEN: Error should be logged
        AND: GNSS type should default to None
        """
        fc_parameters = {param_name: "invalid"}
        realistic_model.set_component_value(("GNSS Receiver", "FC Connection", "Type"), "SERIAL3")
        realistic_model.set_component_value(("GNSS Receiver", "FC Connection", "Protocol"), "uBlox")
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as mock_log:
            realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)
        mock_log.assert_called_once_with("Invalid non-integer value for %s: %s", param_name, "invalid")
        assert realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type")) == "None"
        assert realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Protocol")) == "None"

    @pytest.mark.parametrize("param_name", ["GPS_TYPE", "GPS1_TYPE"])
    def test_set_gnss_type_handles_unknown_gps_type(self, realistic_model, param_name: str) -> None:  # type: ignore[misc]
        """
        Internal GNSS type setter handles unknown GPS_TYPE value.

        GIVEN: FC parameters with unknown GPS_TYPE (999)
        WHEN: Setting GNSS type from parameters
        THEN: Error should be logged
        AND: GNSS type should default to None
        """
        fc_parameters = {param_name: 999}
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as mock_log:
            realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)
        mock_log.assert_called_once_with("%s value %u not in GNSS_RECEIVER_CONNECTION", param_name, 999)
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
        realistic_model.set_component_value(("RC Receiver", "FC Connection", "Type"), "SERIAL2")
        realistic_model.set_component_value(("RC Receiver", "FC Connection", "Protocol"), "CRSF")
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as mock_log:
            realistic_model._set_serial_type_from_fc_parameters(fc_parameters)
        mock_log.assert_called_once_with("Invalid non-integer value for RC_PROTOCOLS %s", "invalid")
        assert realistic_model.get_component_value(("RC Receiver", "FC Connection", "Type")) == "SERIAL2"
        assert realistic_model.get_component_value(("RC Receiver", "FC Connection", "Protocol")) == "CRSF"

    def test_set_serial_type_handles_multiple_rc_protocols(self, realistic_model) -> None:
        """
        Internal serial type setter handles ambiguous RC_PROTOCOLS.

        GIVEN: FC parameters with multiple RC protocols enabled (not power of 2)
        WHEN: Setting serial type from parameters
        THEN: Protocol should not be set due to ambiguity
        """
        fc_parameters = {"RC_PROTOCOLS": 3}  # Not a power of 2
        realistic_model.set_component_value(("RC Receiver", "FC Connection", "Type"), "SERIAL2")
        realistic_model.set_component_value(("RC Receiver", "FC Connection", "Protocol"), "CRSF")
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as mock_log:
            realistic_model._set_serial_type_from_fc_parameters(fc_parameters)
        mock_log.assert_called_once_with(
            "RC_PROTOCOLS has multiple protocols enabled (%d). Cannot determine active protocol.", 3
        )
        assert realistic_model.get_component_value(("RC Receiver", "FC Connection", "Type")) == "SERIAL2"
        assert realistic_model.get_component_value(("RC Receiver", "FC Connection", "Protocol")) == "CRSF"

    def test_set_rc_protocols_identifies_single_enabled_protocol(self, realistic_model) -> None:
        """One known RC protocol bit selects its protocol and supplies the default type."""
        realistic_model.set_component_value(("RC Receiver", "FC Connection", "Type"), None)
        realistic_model.set_component_value(("RC Receiver", "FC Connection", "Protocol"), None)

        realistic_model._process_rc_protocols({"RC_PROTOCOLS": 512})

        assert realistic_model.get_component_value(("RC Receiver", "FC Connection", "Type")) == "RCin/SBUS"
        assert realistic_model.get_component_value(("RC Receiver", "FC Connection", "Protocol")) == "CRSF"

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
            with patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"
            ) as mock_log:
                result = realistic_model._set_serial_type_from_fc_parameters(fc_parameters)
            assert result is False
        mock_log.assert_called_once_with("Invalid non-integer value for SERIAL1_PROTOCOL invalid")

    @pytest.mark.parametrize("first_protocol", ["invalid", 0, 99, 77])
    def test_invalid_or_unsupported_serial_protocol_does_not_skip_later_ports(
        self, realistic_model, first_protocol: str | int
    ) -> None:
        """A bad or unsupported serial protocol does not prevent later valid ports from importing."""
        with (
            patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PORTS",
                ["SERIAL1", "SERIAL2"],
            ),
            patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PROTOCOLS_DICT",
                {
                    "2": {"component": "Telemetry", "protocol": "MAVLink2"},
                    "77": {"protocol": "Unused component"},
                },
            ),
        ):
            realistic_model._set_serial_type_from_fc_parameters(
                {"SERIAL1_PROTOCOL": first_protocol, "SERIAL2_PROTOCOL": 2}
            )

        assert realistic_model.get_component_value(("Telemetry", "FC Connection", "Type")) == "SERIAL2"
        assert realistic_model.get_component_value(("Telemetry", "FC Connection", "Protocol")) == "MAVLink2"

    def test_first_serial_telemetry_port_keeps_precedence(self, realistic_model) -> None:
        """When multiple serial ports provide telemetry, the first configured port remains selected."""
        with (
            patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PORTS",
                ["SERIAL1", "SERIAL2"],
            ),
            patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PROTOCOLS_DICT",
                {"2": {"component": "Telemetry", "protocol": "MAVLink2"}},
            ),
        ):
            realistic_model._set_serial_type_from_fc_parameters({"SERIAL1_PROTOCOL": 2, "SERIAL2_PROTOCOL": 2})

        assert realistic_model.get_component_value(("Telemetry", "FC Connection", "Type")) == "SERIAL1"
        assert realistic_model.get_component_value(("Telemetry", "FC Connection", "Protocol")) == "MAVLink2"

    def test_missing_earlier_serial_parameter_does_not_skip_a_later_valid_port(self, realistic_model) -> None:
        """Import scans later serial ports when earlier port parameters are absent."""
        with (
            patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PORTS",
                ["SERIAL1", "SERIAL2"],
            ),
            patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PROTOCOLS_DICT",
                {"2": {"component": "Telemetry", "protocol": "MAVLink2"}},
            ),
        ):
            realistic_model._set_serial_type_from_fc_parameters({"SERIAL2_PROTOCOL": 2})

        assert realistic_model.get_component_value(("Telemetry", "FC Connection", "Type")) == "SERIAL2"
        assert realistic_model.get_component_value(("Telemetry", "FC Connection", "Protocol")) == "MAVLink2"

    def test_missing_serial_protocol_component_does_not_skip_later_ports(self, realistic_model) -> None:
        """A protocol entry without a component is skipped while later ports are still inspected."""
        with (
            patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PORTS",
                ["SERIAL1", "SERIAL2"],
            ),
            patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PROTOCOLS_DICT",
                {
                    "77": {"protocol": "Unused component"},
                    "2": {"component": "Telemetry", "protocol": "MAVLink2"},
                },
            ),
        ):
            realistic_model._set_serial_type_from_fc_parameters({"SERIAL1_PROTOCOL": 77, "SERIAL2_PROTOCOL": 2})

        assert realistic_model.get_component_value(("Telemetry", "FC Connection", "Type")) == "SERIAL2"

    def test_serial_gnss_import_keeps_the_first_receiver_port(self, realistic_model) -> None:
        """The first serial GNSS port remains selected when firmware reports multiple receivers."""
        with (
            patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PORTS",
                ["SERIAL1", "SERIAL2"],
            ),
            patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PROTOCOLS_DICT",
                {"5": {"component": "GNSS Receiver", "protocol": "uBlox"}},
            ),
        ):
            realistic_model._set_serial_type_from_fc_parameters({"SERIAL1_PROTOCOL": 5, "SERIAL2_PROTOCOL": 5})

        assert realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type")) == "SERIAL1"
        assert realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Protocol")) == "uBlox"

    def test_serial_esc_control_connection_populates_both_directions(self, realistic_model) -> None:
        """A serial ESC control protocol configures the shared FC-to-ESC and ESC-to-FC connection."""
        with (
            patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PORTS",
                ["SERIAL1"],
            ),
            patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PROTOCOLS_DICT",
                {"23": {"component": "ESC", "protocol": "FETtecOneWire"}},
            ),
        ):
            is_serial_esc = realistic_model._set_serial_type_from_fc_parameters({"SERIAL1_PROTOCOL": 23})

        assert is_serial_esc is True
        assert realistic_model.get_component_value(("ESC", "FC->ESC Connection", "Type")) == "SERIAL1"
        assert realistic_model.get_component_value(("ESC", "FC->ESC Connection", "Protocol")) == "FETtecOneWire"
        assert realistic_model.get_component_value(("ESC", "ESC->FC Telemetry", "Type")) == "SERIAL1"
        assert realistic_model.get_component_value(("ESC", "ESC->FC Telemetry", "Protocol")) == "FETtecOneWire"

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
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as mock_log:
            realistic_model._set_esc_type_from_fc_parameters(fc_parameters, doc)
        mock_log.assert_called_once_with("Invalid non-integer value for MOT_PWM_TYPE %s", "invalid")
        assert realistic_model.get_component_value(("ESC", "FC->ESC Connection", "Type")) == "Main Out"

    def test_missing_motor_pwm_type_uses_the_zero_default(self, realistic_model) -> None:
        """A missing MOT_PWM_TYPE uses firmware's default value zero when metadata is available."""
        realistic_model._set_esc_type_from_fc_parameters(
            {}, {"MOT_PWM_TYPE": {"values": {"0": "Normal", "1": "OneShot"}}}
        )

        assert realistic_model.get_component_value(("ESC", "FC->ESC Connection", "Protocol")) == "Normal"

    @pytest.mark.parametrize(
        ("telemetry_type", "telemetry_protocol"),
        [("SERIAL3", "Scripting"), ("CAN1", "DroneCAN")],
    )
    def test_dshot_import_preserves_a_dedicated_telemetry_connection(
        self, realistic_model, telemetry_type: str, telemetry_protocol: str
    ) -> None:
        """DShot control import does not replace an independently detected serial or CAN back-channel."""
        realistic_model.set_component_value(("ESC", "ESC->FC Telemetry", "Type"), telemetry_type)
        realistic_model.set_component_value(("ESC", "ESC->FC Telemetry", "Protocol"), telemetry_protocol)

        realistic_model._set_esc_type_from_fc_parameters(
            {"MOT_PWM_TYPE": 6}, {"MOT_PWM_TYPE": {"values": {"6": "DShot600"}}}
        )

        assert realistic_model.get_component_value(("ESC", "ESC->FC Telemetry", "Type")) == telemetry_type
        assert realistic_model.get_component_value(("ESC", "ESC->FC Telemetry", "Protocol")) == telemetry_protocol

    def test_non_dshot_import_preserves_a_dedicated_serial_telemetry_connection(self, realistic_model) -> None:
        """A non-DShot control protocol leaves an already imported serial telemetry link intact."""
        realistic_model.set_component_value(("ESC", "ESC->FC Telemetry", "Type"), "SERIAL4")
        realistic_model.set_component_value(("ESC", "ESC->FC Telemetry", "Protocol"), "ESC Telemetry")

        realistic_model._set_esc_type_from_fc_parameters(
            {"MOT_PWM_TYPE": 0}, {"MOT_PWM_TYPE": {"values": {"0": "Normal"}}}
        )

        assert realistic_model.get_component_value(("ESC", "ESC->FC Telemetry", "Type")) == "SERIAL4"
        assert realistic_model.get_component_value(("ESC", "ESC->FC Telemetry", "Protocol")) == "ESC Telemetry"

    def test_esc_dictionary_fallback_uses_the_selected_firmware(self, realistic_model, monkeypatch) -> None:
        """When parameter metadata is absent, ESC protocol lookup uses the active firmware dictionary."""
        realistic_model.set_component_value(("Flight Controller", "Firmware", "Type"), "ArduPlane")
        requested_firmware_types: list[str] = []

        def connection_options(firmware_type: str) -> dict:
            requested_firmware_types.append(firmware_type)
            return {"6": {"protocol": "PlaneDShot", "type": ("Main Out",)}}

        monkeypatch.setattr(
            "ardupilot_methodic_configurator.data_model_vehicle_components_import.get_esc_connection_sub_dict",
            connection_options,
        )

        realistic_model._set_esc_type_from_fc_parameters({"MOT_PWM_TYPE": 6}, {})

        assert realistic_model.get_component_value(("ESC", "FC->ESC Connection", "Protocol")) == "PlaneDShot"
        assert requested_firmware_types == ["ArduPlane"]

    def test_set_battery_type_handles_invalid_value(self, realistic_model) -> None:
        """
        Internal battery type setter handles invalid BATT_MONITOR value.

        GIVEN: FC parameters with non-integer BATT_MONITOR value
        WHEN: Setting battery type from parameters
        THEN: Error should be logged
        AND: System should not crash
        """
        fc_parameters = {"BATT_MONITOR": "invalid"}
        realistic_model.set_component_value(("Battery Monitor", "FC Connection", "Type"), "Analog")
        realistic_model.set_component_value(("Battery Monitor", "FC Connection", "Protocol"), "Analog Voltage and Current")
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as mock_log:
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)
        assert mock_log.call_args.args[0] == "Error processing BATT_MONITOR parameter: %s"
        assert "invalid" in mock_log.call_args.args[1]
        assert realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Type")) == "Analog"
        assert (
            realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Protocol"))
            == "Analog Voltage and Current"
        )

    def test_set_battery_type_handles_key_error(self, realistic_model) -> None:
        """
        Internal battery type setter handles unknown BATT_MONITOR value.

        GIVEN: FC parameters with BATT_MONITOR value not in dictionary
        WHEN: Setting battery type from parameters
        THEN: KeyError should be handled
        AND: Error should be logged
        """  # pylint: disable=duplicate-code  # Common error handling test pattern
        fc_parameters = {"BATT_MONITOR": 999}
        realistic_model.set_component_value(("Battery Monitor", "FC Connection", "Type"), "Analog")
        realistic_model.set_component_value(("Battery Monitor", "FC Connection", "Protocol"), "Analog Voltage and Current")
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as mock_log:
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)
        mock_log.assert_called_once_with("BATT_MONITOR value %s not found in BATT_MONITOR_CONNECTION", 999)
        assert realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Type")) == "Analog"
        assert (
            realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Protocol"))
            == "Analog Voltage and Current"
        )
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
        realistic_model.set_component_value(("Battery Monitor", "FC Connection", "Type"), "Analog")
        realistic_model.set_component_value(("Battery Monitor", "FC Connection", "Protocol"), "Analog Voltage and Current")
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as mock_log:
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)
        assert mock_log.call_args.args[0] == "Error processing BATT_MONITOR parameter: %s"
        assert "NoneType" in mock_log.call_args.args[1]
        assert realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Type")) == "Analog"
        assert (
            realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Protocol"))
            == "Analog Voltage and Current"
        )
        # pylint: enable=duplicate-code

    def test_set_battery_type_handles_tuple_type_values(self, realistic_model) -> None:
        """
        Internal battery type setter handles tuple-type configuration values.

        GIVEN: Battery configuration with tuple values for type and protocol
        WHEN: Setting battery type from parameters
        THEN: First element of each tuple should be used
        """
        with patch(
            "ardupilot_methodic_configurator.data_model_vehicle_components_import.BATT_MONITOR_CONNECTION",
            {"4": {"type": ("Analog", "Digital"), "protocol": ("Voltage", "Current")}},
        ):
            fc_parameters = {"BATT_MONITOR": 4}
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)
            batt_type = realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Type"))
            batt_protocol = realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Protocol"))
            assert batt_type == "Analog"
            assert batt_protocol == "Voltage"

    def test_set_battery_type_uses_documented_defaults_when_metadata_fields_are_missing(self, realistic_model) -> None:
        """Missing connection fields retain the documented type and protocol defaults."""
        with patch(
            "ardupilot_methodic_configurator.data_model_vehicle_components_import.BATT_MONITOR_CONNECTION",
            {"4": {}},
        ):
            realistic_model._set_battery_type_from_fc_parameters({"BATT_MONITOR": 4})

        assert realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Type")) == "None"
        assert realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Protocol")) == "Disabled"

    @pytest.mark.parametrize(("bus", "expected"), [(1, "I2C2"), (99, "I2C1"), ("invalid", "I2C1")])
    def test_set_battery_type_selects_and_bounds_i2c_bus(self, realistic_model, bus: int | str, expected: str) -> None:
        """The BATT_I2C_BUS index selects the matching I2C port and invalid indices fall back to I2C1."""
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning") as log_warning:
            realistic_model._set_battery_type_from_fc_parameters({"BATT_MONITOR": 5, "BATT_I2C_BUS": bus})

        assert realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Type")) == expected
        if bus == 99:
            log_warning.assert_called_once_with("BATT_I2C_BUS value %d out of range (0-%d), defaulting to first bus", 99, 3)
        elif bus == "invalid":
            log_warning.assert_called_once_with("Invalid BATT_I2C_BUS value, defaulting to first bus")
        else:
            log_warning.assert_not_called()

    def test_motor_pole_import_uses_selected_firmware_esc_dictionary(self, realistic_model) -> None:
        """DShot pole detection looks up the connection mapping for the selected firmware."""
        realistic_model.set_component_value(("Flight Controller", "Firmware", "Type"), "ArduCopter")
        realistic_model.set_component_value(("Motors", "Specifications", "Poles"), 99)

        with patch.object(
            _import_module,
            "get_esc_connection_sub_dict",
            wraps=_import_module.get_esc_connection_sub_dict,
        ) as get_esc_dict:
            realistic_model._set_motor_poles_from_fc_parameters({"MOT_PWM_TYPE": 6, "SERVO_BLH_POLES": 14})

        get_esc_dict.assert_called_once_with("ArduCopter")
        assert realistic_model.get_component_value(("Motors", "Specifications", "Poles")) == 14

    def test_motor_pole_import_uses_empty_firmware_key_when_type_is_unset(self, realistic_model) -> None:
        """A missing firmware type is normalized to an empty dictionary lookup key."""
        original_get = realistic_model.get_component_value
        firmware_path = ("Flight Controller", "Firmware", "Type")

        def get_component_value(path: tuple[str, str, str]) -> object:
            if path == firmware_path:
                return None
            return original_get(path)

        with (
            patch.object(realistic_model, "get_component_value", side_effect=get_component_value),
            patch.object(_import_module, "get_esc_connection_sub_dict", return_value={}) as get_esc_dict,
        ):
            realistic_model._set_motor_poles_from_fc_parameters({"MOT_PWM_TYPE": 6})

        get_esc_dict.assert_called_once_with("")

    def test_unknown_motor_pwm_type_does_not_break_motor_pole_import(self, realistic_model) -> None:
        """An unknown PWM type with no matching metadata leaves the current pole count untouched."""
        realistic_model.set_component_value(("Motors", "Specifications", "Poles"), 99)

        realistic_model._set_motor_poles_from_fc_parameters({"MOT_PWM_TYPE": 999, "SERVO_BLH_POLES": 14})

        assert realistic_model.get_component_value(("Motors", "Specifications", "Poles")) == 99

    def test_fettec_pole_count_requires_mask_and_pole_value(self, realistic_model) -> None:
        """A FETtec pole count is ignored unless both the mask and pole count are present."""
        realistic_model.set_component_value(("Motors", "Specifications", "Poles"), 99)

        realistic_model._set_motor_poles_from_fc_parameters({"MOT_PWM_TYPE": 0, "SERVO_FTW_POLES": 12})

        assert realistic_model.get_component_value(("Motors", "Specifications", "Poles")) == 99

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

    @pytest.mark.parametrize("capacity", [0, -100])
    def test_battery_capacity_rejection_logs_exact_value(self, realistic_model, capacity: int) -> None:
        """Zero and negative capacities are rejected with the exact FC value in the warning."""
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning") as log_warning:
            realistic_model._import_bat_values_from_fc(
                BatteryVoltageSpecs(0, 3.0, 4.2, "Lipo", {"BATT_CAPACITY": capacity})
            )

        log_warning.assert_called_once_with("BATT_CAPACITY is zero or negative: %s", capacity)

    @pytest.mark.parametrize("capacity", [None, "unknown"])
    def test_battery_capacity_conversion_error_logs_exact_parameter_and_error(self, realistic_model, capacity) -> None:
        """Invalid capacity values report their conversion failure with the parameter name."""
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as log_error:
            realistic_model._import_bat_values_from_fc(
                BatteryVoltageSpecs(0, 3.0, 4.2, "Lipo", {"BATT_CAPACITY": capacity})
            )

        log_error.assert_called_once()
        args = log_error.call_args.args
        assert args[0] == "Error processing BATT_CAPACITY parameter: %s"
        assert args[1].startswith(("int() argument must be a string", "invalid literal for int()"))

    def test_plane_battery_import_preserves_template_values_when_import_file_is_sparse(self, realistic_model) -> None:
        """
        Sparse Plane imports preserve battery values already supplied by the template.

        ArduPlane does not define Copter's MOT_BAT_VOLT_MAX parameter, and an imported
        difference file may omit BATT_CAPACITY and all voltage thresholds when they match
        the template. The component editor must not clear the existing battery data.
        """
        realistic_model.set_component_value(("Flight Controller", "Firmware", "Type"), "ArduPlane")
        battery_specs = realistic_model.get_component_data()["Components"]["Battery"]["Specifications"]
        initial_specs = battery_specs.copy()

        realistic_model._set_battery_type_from_fc_parameters({"BATT_MONITOR": 0})

        assert realistic_model.get_component_data()["Components"]["Battery"]["Specifications"] == initial_specs

    def test_copter_battery_import_preserves_template_values_when_import_file_is_sparse(self, realistic_model) -> None:
        """
        Sparse Copter imports preserve battery values already supplied by the template.

        GIVEN: A Copter template with a validated battery specification
        WHEN: An imported difference file omits all battery voltage thresholds
        THEN: The existing battery specification remains unchanged
        """
        battery_specs = realistic_model.get_component_data()["Components"]["Battery"]["Specifications"]
        initial_specs = battery_specs.copy()

        realistic_model._set_battery_type_from_fc_parameters({"BATT_MONITOR": 0})

        assert realistic_model.get_component_data()["Components"]["Battery"]["Specifications"] == initial_specs

    def test_plane_battery_import_uses_batt_thresholds_without_copter_motor_voltage_parameters(self, realistic_model) -> None:
        """ArduPlane battery thresholds import correctly without MOT_BAT_VOLT_MAX/MIN."""
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")

        realistic_model._set_battery_type_from_fc_parameters(
            {
                "BATT_MONITOR": 0,
                "BATT_CAPACITY": 3300,
                "BATT_ARM_VOLT": 23.2998,
                "BATT_LOW_VOLT": 22.8,
                "BATT_CRT_VOLT": 21.0,
            }
        )

        battery_specs = realistic_model.get_component_data()["Components"]["Battery"]["Specifications"]
        assert battery_specs["Number of cells"] == 6
        assert battery_specs["Capacity mAh"] == 3300
        assert battery_specs["Volt per cell arm"] == pytest.approx(3.8833)
        assert battery_specs["Volt per cell low"] == pytest.approx(3.8)
        assert battery_specs["Volt per cell crit"] == pytest.approx(3.5)

    def test_estimate_cell_count_from_mot_bat_volt_max(self, realistic_model) -> None:
        """
        Cell count is estimated from MOT_BAT_VOLT_MAX parameter.

        GIVEN: FC with MOT_BAT_VOLT_MAX for 4S battery
        WHEN: Estimating battery cell count
        THEN: Should calculate 4 cells correctly
        """
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")
        fc_parameters = {"MOT_BAT_VOLT_MAX": 16.8}
        realistic_model._estimate_battery_cell_count(fc_parameters)
        assert realistic_model.get_component_value(("Battery", "Specifications", "Number of cells")) == 4

    def test_estimate_cell_count_from_batt_low_volt(self, realistic_model) -> None:
        """
        Cell count is estimated from BATT_LOW_VOLT when MOT_BAT_VOLT_MAX unavailable.

        GIVEN: FC with only BATT_LOW_VOLT configured
        WHEN: Estimating battery cell count
        THEN: Should use BATT_LOW_VOLT for estimation
        """
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")
        fc_parameters = {"BATT_LOW_VOLT": 21.6}  # 6S
        realistic_model._estimate_battery_cell_count(fc_parameters)
        assert realistic_model.get_component_value(("Battery", "Specifications", "Number of cells")) == 6

    def test_estimate_cell_count_from_batt_crt_volt(self, realistic_model) -> None:
        """
        Cell count is estimated from BATT_CRT_VOLT as last resort.

        GIVEN: FC with only BATT_CRT_VOLT configured
        WHEN: Estimating battery cell count
        THEN: Should use BATT_CRT_VOLT for estimation
        """
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")
        fc_parameters = {"BATT_CRT_VOLT": 9.9}  # 3S
        realistic_model._estimate_battery_cell_count(fc_parameters)
        assert realistic_model.get_component_value(("Battery", "Specifications", "Number of cells")) == 3

    def test_estimate_cell_count_respects_priority(self, realistic_model) -> None:
        """
        Cell count estimation prioritizes MOT_BAT_VOLT_MAX over other parameters.

        GIVEN: FC with all voltage parameters set
        WHEN: Estimating battery cell count
        THEN: Should use MOT_BAT_VOLT_MAX (highest priority)
        """
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")
        fc_parameters = {
            "MOT_BAT_VOLT_MAX": 12.6,  # 3S
            "BATT_LOW_VOLT": 14.4,  # Would be 4S
            "BATT_CRT_VOLT": 16.5,  # Would be 5S
        }
        realistic_model._estimate_battery_cell_count(fc_parameters)
        assert realistic_model.get_component_value(("Battery", "Specifications", "Number of cells")) == 3

    def test_estimate_cell_count_handles_zero_voltage(self, realistic_model) -> None:
        """
        Zero voltage values are ignored during cell count estimation.

        GIVEN: FC with zero voltage parameters
        WHEN: Estimating battery cell count
        THEN: Cell count should not be set
        """
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")
        initial_cells = realistic_model.get_component_value(("Battery", "Specifications", "Number of cells"))
        fc_parameters = {"MOT_BAT_VOLT_MAX": 0}
        realistic_model._estimate_battery_cell_count(fc_parameters)
        assert realistic_model.get_component_value(("Battery", "Specifications", "Number of cells")) == initial_cells

    def test_estimate_cell_count_validates_range(self, realistic_model) -> None:
        """
        Unrealistic cell count estimations are rejected.

        GIVEN: FC with voltage that would estimate >50 cells
        WHEN: Estimating battery cell count
        THEN: Cell count should not be set (out of range)
        """
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")
        initial_cells = realistic_model.get_component_value(("Battery", "Specifications", "Number of cells"))
        fc_parameters = {"MOT_BAT_VOLT_MAX": 300.0}  # ~71 cells
        realistic_model._estimate_battery_cell_count(fc_parameters)
        assert realistic_model.get_component_value(("Battery", "Specifications", "Number of cells")) == initial_cells

    def test_set_battery_type_warns_when_batt_monitor_not_in_fc_parameters(self, realistic_model) -> None:
        """
        System logs a warning when BATT_MONITOR is absent from FC parameters.

        GIVEN: FC parameters with no BATT_MONITOR key
        WHEN: Setting battery type from FC parameters
        THEN: A warning should be logged about missing BATT_MONITOR
        AND: The rest of the battery processing (chemistry, cells) still runs without crash
        """
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning") as mock_warn:
            realistic_model._set_battery_type_from_fc_parameters({})
        mock_warn.assert_called_once_with("BATT_MONITOR parameter not found in fc_parameters")

    def test_set_battery_type_uses_default_chemistry_when_detection_returns_invalid_name(self, realistic_model) -> None:
        """
        System falls back to BATTERY_DEFAULT_CHEMISTRY when detected chemistry is not a valid name.

        GIVEN: FC parameters where chemistry detection returns an unrecognised chemistry string
        WHEN: Setting battery type from FC parameters
        THEN: The invalid chemistry is replaced with BATTERY_DEFAULT_CHEMISTRY
        AND: Subsequent voltage limit lookups use the default chemistry without error
        """
        assert BATTERY_DEFAULT_CHEMISTRY in BatteryCell.chemistries()

        with (
            patch.object(realistic_model, "_detect_battery_chemistry_from_voltages", return_value="InvalidChemistry"),
            patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning"),
            patch.object(realistic_model, "_estimate_battery_cell_count", return_value=4) as estimate,
            patch.object(realistic_model, "_import_bat_values_from_fc") as import_values,
        ):
            realistic_model._set_battery_type_from_fc_parameters({"BATT_MONITOR": 4})

        estimate.assert_called_once_with({"BATT_MONITOR": 4}, BATTERY_DEFAULT_CHEMISTRY)
        specs = import_values.call_args.args[0]
        assert specs.detected_chemistry == BATTERY_DEFAULT_CHEMISTRY
        assert specs.limit_min == BatteryCell.limit_min_voltage(BATTERY_DEFAULT_CHEMISTRY)
        assert specs.limit_max == BatteryCell.limit_max_voltage(BATTERY_DEFAULT_CHEMISTRY)

    def test_set_battery_type_preserves_valid_current_chemistry_when_detection_is_unavailable(self, realistic_model) -> None:
        """Unavailable voltage evidence preserves a valid chemistry already selected in the model."""
        current_chemistry = "LiIon"
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), current_chemistry)

        with (
            patch.object(realistic_model, "_detect_battery_chemistry_from_voltages", return_value=None),
            patch.object(realistic_model, "_estimate_battery_cell_count", return_value=4) as estimate,
            patch.object(realistic_model, "_import_bat_values_from_fc") as import_values,
            patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning"),
        ):
            realistic_model._set_battery_type_from_fc_parameters({"BATT_MONITOR": 4, "BATT_ARM_VOLT": 20.0})

        estimate.assert_called_once_with({"BATT_MONITOR": 4, "BATT_ARM_VOLT": 20.0}, current_chemistry)
        specs = import_values.call_args.args[0]
        assert specs.detected_chemistry == current_chemistry
        assert specs.limit_min == BatteryCell.limit_min_voltage(current_chemistry)
        assert specs.limit_max == BatteryCell.limit_max_voltage(current_chemistry)

    def test_estimate_battery_cell_count_returns_zero_when_cell_path_not_in_validation_rules(self, realistic_model) -> None:
        """
        Battery cell count estimation returns 0 when the cell path is absent from VALIDATION_RULES.

        GIVEN: VALIDATION_RULES patched to be empty (no cell-count entry)
        WHEN: Estimating battery cell count with a valid voltage parameter
        THEN: Should return 0 (validation guard cannot be checked)
        """
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")

        with patch.object(ComponentDataModelValidation, "VALIDATION_RULES", {}):
            result = realistic_model._estimate_battery_cell_count({"MOT_BAT_VOLT_MAX": 16.8})

        assert result == 0

    @pytest.mark.parametrize(
        ("parameter", "value"),
        [
            ("MOT_BAT_VOLT_MAX", "invalid"),
            ("BATT_LOW_VOLT", "invalid"),
            ("BATT_CRT_VOLT", "invalid"),
            ("BATT_ARM_VOLT", "invalid"),
            ("MOT_BAT_VOLT_MIN", "invalid"),
        ],
    )
    def test_invalid_voltage_fallback_reports_the_parameter_name(self, realistic_model, parameter, value) -> None:
        """A malformed preferred reading reports its source before fallback continues."""
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as log_error:
            realistic_model._estimate_battery_cell_count({parameter: value})

        assert any(parameter in " ".join(str(part) for part in call.args) for call in log_error.call_args_list)

    @pytest.mark.parametrize(
        ("parameter", "spec"),
        [
            ("MOT_BAT_VOLT_MAX", "Volt per cell max"),
            ("BATT_LOW_VOLT", "Volt per cell low"),
            ("BATT_CRT_VOLT", "Volt per cell crit"),
            ("BATT_ARM_VOLT", "Volt per cell arm"),
            ("MOT_BAT_VOLT_MIN", "Volt per cell min"),
        ],
    )
    def test_each_voltage_fallback_uses_its_source_name_and_spec(self, realistic_model, parameter, spec) -> None:
        """Interpret each FC voltage reading with its matching chemistry recommendation."""
        voltage = 12.0
        with patch.object(realistic_model, "_estimate_cells_from_voltage_param_default", return_value=3) as estimate:
            assert realistic_model._estimate_battery_cell_count({parameter: voltage}) == 3

        estimate.assert_called_once_with(parameter, voltage, spec, "Lipo")

    @pytest.mark.parametrize("bound", ["min", "max"])
    def test_existing_cell_count_at_validation_boundary_is_preserved(self, realistic_model, bound) -> None:
        """Sparse parameter imports preserve a template cell count at either allowed boundary."""
        cell_path = ("Battery", "Specifications", "Number of cells")
        _value_type, (minimum, maximum), _documentation = ComponentDataModelValidation.VALIDATION_RULES[cell_path]
        existing_cells = minimum if bound == "min" else maximum
        realistic_model.set_component_value(cell_path, existing_cells)

        assert realistic_model._estimate_battery_cell_count({}) == existing_cells

    def test_invalid_existing_cell_count_logs_clear_failure(self, realistic_model) -> None:
        """A sparse import with no usable template cell count reports why estimation failed."""
        with (
            patch.object(realistic_model, "get_component_value", return_value=None),
            patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as log_error,
        ):
            assert realistic_model._estimate_battery_cell_count({}) == 0

        log_error.assert_called_once_with("All volt per cell values are zero or invalid; cannot estimate battery cell count")

    @pytest.mark.parametrize(("cell_count", "voltage"), [(2, 8.4), (4, 16.8)])
    def test_estimated_cell_count_accepts_validation_boundaries(self, realistic_model, cell_count, voltage) -> None:
        """Valid voltage estimates at the declared minimum and maximum are accepted inclusively."""
        cell_path = ("Battery", "Specifications", "Number of cells")
        original_rule = ComponentDataModelValidation.VALIDATION_RULES[cell_path]
        bounded_rule = (original_rule[0], (2, 4), original_rule[2])
        with patch.object(ComponentDataModelValidation, "VALIDATION_RULES", {cell_path: bounded_rule}):
            assert realistic_model._estimate_battery_cell_count({"MOT_BAT_VOLT_MAX": voltage}) == cell_count

    def test_out_of_range_estimate_logs_count_and_both_limits(self, realistic_model) -> None:
        """Explain the rejected count and inclusive allowed range when an estimate is outside it."""
        cell_path = ("Battery", "Specifications", "Number of cells")
        original_rule = ComponentDataModelValidation.VALIDATION_RULES[cell_path]
        bounded_rule = (original_rule[0], (2, 4), original_rule[2])
        with (
            patch.object(ComponentDataModelValidation, "VALIDATION_RULES", {cell_path: bounded_rule}),
            patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as log_error,
        ):
            assert realistic_model._estimate_battery_cell_count({"MOT_BAT_VOLT_MAX": 21.0}) == 0

        log_error.assert_called_once_with("Estimated battery cell count %s is out of valid range (%d to %d)", 5, 2, 4)

    def test_set_battery_type_handles_string_type_in_batt_monitor_connection(self, realistic_model) -> None:
        """
        Battery type setter handles non-list (string) type in BATT_MONITOR_CONNECTION.

        GIVEN: BATT_MONITOR_CONNECTION patched to have a plain string 'type' (not a list)
        WHEN: Setting battery type with that BATT_MONITOR value
        THEN: isinstance(fc_conn_type, list) is False — the list-handling block is skipped
              and the string type is set directly on the Battery Monitor component
        """
        with patch(
            "ardupilot_methodic_configurator.data_model_vehicle_components_import.BATT_MONITOR_CONNECTION",
            {"9": {"type": "Other", "protocol": "ESC"}},
        ):
            realistic_model._set_battery_type_from_fc_parameters({"BATT_MONITOR": 9})

        batt_type = realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Type"))
        assert batt_type == "Other"
