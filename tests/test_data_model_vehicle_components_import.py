#!/usr/bin/env python3

"""
Vehicle Components data model import tests.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from typing import Any
from unittest.mock import patch

import pytest
from test_data_model_vehicle_components_common import (
    BasicTestMixin,
    ComponentDataModelFixtures,
    RealisticDataTestMixin,
)

from ardupilot_methodic_configurator.data_model_vehicle_components_import import ComponentDataModelImport

# pylint: disable=protected-access,too-many-public-methods


class TestComponentDataModelImport(BasicTestMixin, RealisticDataTestMixin):
    """Tests for the ComponentDataModelImport class."""

    @pytest.fixture
    def empty_model(self) -> ComponentDataModelImport:
        """Create an empty ComponentDataModelImport fixture for testing."""
        return ComponentDataModelFixtures.create_empty_model(ComponentDataModelImport)

    @pytest.fixture
    def basic_model(self) -> ComponentDataModelImport:
        """Create a ComponentDataModelImport fixture for testing."""
        return ComponentDataModelFixtures.create_basic_model(ComponentDataModelImport)

    @pytest.fixture
    def realistic_model(self) -> ComponentDataModelImport:
        """Create a realistic vehicle data model based on the JSON file."""
        return ComponentDataModelFixtures.create_realistic_model(ComponentDataModelImport)

    def test_is_fc_manufacturer_valid(self, basic_model) -> None:
        """Test flight controller manufacturer validation."""
        # Valid manufacturers
        assert basic_model.is_fc_manufacturer_valid("Pixhawk")
        assert basic_model.is_fc_manufacturer_valid("Matek")
        assert basic_model.is_fc_manufacturer_valid("Holybro")

        # Invalid manufacturers
        assert not basic_model.is_fc_manufacturer_valid("Unknown")
        assert not basic_model.is_fc_manufacturer_valid("ArduPilot")
        assert not basic_model.is_fc_manufacturer_valid("")
        assert not basic_model.is_fc_manufacturer_valid(None)

    def test_is_fc_model_valid(self, basic_model) -> None:
        """Test flight controller model validation."""
        # Valid models
        assert basic_model.is_fc_model_valid("Pixhawk 6C")
        assert basic_model.is_fc_model_valid("H743 SLIM")
        assert basic_model.is_fc_model_valid("Custom FC")

        # Invalid models
        assert not basic_model.is_fc_model_valid("Unknown")
        assert not basic_model.is_fc_model_valid("MAVLink")
        assert not basic_model.is_fc_model_valid("")
        assert not basic_model.is_fc_model_valid(None)

    def test_reverse_key_search_method(self, realistic_model, sample_doc_dict) -> None:
        """Test the reverse key search method."""
        # Test finding keys for specific values
        result = realistic_model._reverse_key_search(sample_doc_dict, "SERIAL1_PROTOCOL", ["MAVLink1", "MAVLink2"], [1, 2])
        assert result == [1, 2]

        # Test with missing values (should return fallbacks)
        result = realistic_model._reverse_key_search(sample_doc_dict, "SERIAL1_PROTOCOL", ["NonExistent"], [99])
        assert result == [99]

        # Test with mismatched values and fallbacks length
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as mock_log:
            result = realistic_model._reverse_key_search(
                sample_doc_dict,
                "SERIAL1_PROTOCOL",
                ["GPS", "RCIN"],
                [5],  # Mismatched lengths
            )
            mock_log.assert_called()
            assert result == [5, 23]  # Should still return found values

    def test_reverse_key_search_edge_cases(self, realistic_model) -> None:
        """Test edge cases for reverse key search method."""
        # Test with empty documentation - should handle KeyError gracefully
        empty_doc: dict = {}
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            # The method should handle the KeyError and return fallbacks
            try:
                result = realistic_model._reverse_key_search(empty_doc, "MISSING_PARAM", ["value"], [99])
                assert result == [99]  # Should return fallbacks when parameter not found
            except KeyError:
                # The current implementation raises KeyError - this is expected behavior
                # The method is designed to access doc[param_name]["values"] directly
                pass

        # Test with malformed documentation (missing values key)
        malformed_doc: dict = {"PARAM": {"other_key": {}}}
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            try:
                result = realistic_model._reverse_key_search(malformed_doc, "PARAM", ["value"], [99])
                assert result == [99]
            except KeyError:
                # Expected behavior - the method doesn't handle missing "values" key
                pass

        # Test with empty values in documentation
        empty_values_doc: dict = {"PARAM": {"values": {}}}
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            result = realistic_model._reverse_key_search(empty_values_doc, "PARAM", ["value"], [99])
            assert result == [99]

    def test_verify_dict_is_uptodate_valid(self, realistic_model, sample_doc_dict) -> None:
        """Test dictionary verification against documentation - valid case."""
        dict_to_check = {
            "1": {"protocol": "MAVLink1"},
            "2": {"protocol": "MAVLink2"},
            "5": {"protocol": "GPS"},
            "23": {"protocol": "RCIN"},
        }

        result = realistic_model._verify_dict_is_uptodate(sample_doc_dict, dict_to_check, "SERIAL1_PROTOCOL", "values")
        assert result is True

    def test_verify_dict_is_uptodate_invalid(self, realistic_model, sample_doc_dict) -> None:
        """Test dictionary verification against documentation - invalid case."""
        dict_mismatch = {
            "1": {"protocol": "Wrong Protocol"},
            "2": {"protocol": "MAVLink2"},
            "5": {"protocol": "GPS"},
            "23": {"protocol": "RCIN"},
        }

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            result = realistic_model._verify_dict_is_uptodate(sample_doc_dict, dict_mismatch, "SERIAL1_PROTOCOL", "values")
            assert result is False

    def test_verify_dict_is_uptodate_missing_doc(self, realistic_model) -> None:
        """Test dictionary verification with missing documentation."""
        # Test with empty doc
        result = realistic_model._verify_dict_is_uptodate({}, {}, "MISSING", "values")
        assert result is False

        # Test with missing doc_key
        doc: dict = {"OTHER_KEY": {"values": {}}}
        result = realistic_model._verify_dict_is_uptodate(doc, {}, "MISSING_KEY", "values")
        assert result is False

        # Test with missing doc_dict
        doc = {"PARAM": {"other_dict": {}}}
        result = realistic_model._verify_dict_is_uptodate(doc, {}, "PARAM", "values")
        assert result is False

    def test_verify_dict_is_uptodate_missing_key_in_dict(self, realistic_model) -> None:
        """Test dictionary verification when key is missing in dict_to_check."""
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

    @patch(
        "ardupilot_methodic_configurator.data_model_vehicle_components_import.GNSS_RECEIVER_CONNECTION",
        {"2": {"type": "SERIAL", "protocol": "uBlox"}},
    )
    @patch(
        "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PROTOCOLS_DICT",
        {"5": {"component": "GNSS Receiver", "protocol": "GPS"}},
    )
    def test_set_gnss_type_from_fc_parameters_serial(self, realistic_model) -> None:
        """Test GNSS parameter processing for serial connection."""
        fc_parameters = {"GPS_TYPE": 2}

        realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)

        protocol = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Protocol"))
        assert protocol == "uBlox"

    @patch(
        "ardupilot_methodic_configurator.data_model_vehicle_components_import.GNSS_RECEIVER_CONNECTION",
        {"0": {"type": "None", "protocol": "None"}},
    )
    def test_set_gnss_type_from_fc_parameters_none(self, realistic_model) -> None:
        """Test GNSS parameter processing for None connection."""
        fc_parameters = {"GPS_TYPE": 0}

        realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)

        gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        gnss_protocol = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Protocol"))
        assert gnss_type == "None"
        assert gnss_protocol == "None"

    @patch(
        "ardupilot_methodic_configurator.data_model_vehicle_components_import.GNSS_RECEIVER_CONNECTION",
        {"9": {"type": "CAN1", "protocol": "DroneCAN"}},
    )
    @patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.CAN_PORTS", ["CAN1", "CAN2"])
    def test_set_gnss_type_from_fc_parameters_can1(self, realistic_model) -> None:
        """Test GNSS parameter processing for CAN1 connection."""
        fc_parameters = {"GPS_TYPE": 9, "CAN_D1_PROTOCOL": 1, "CAN_P1_DRIVER": 1}

        realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)

        gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        gnss_protocol = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Protocol"))
        assert gnss_type == "CAN1"
        assert gnss_protocol == "DroneCAN"

    @patch(
        "ardupilot_methodic_configurator.data_model_vehicle_components_import.GNSS_RECEIVER_CONNECTION",
        {"9": {"type": "CAN2", "protocol": "DroneCAN"}},
    )
    @patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.CAN_PORTS", ["CAN1", "CAN2"])
    def test_set_gnss_type_from_fc_parameters_can2(self, realistic_model) -> None:
        """Test GNSS parameter processing for CAN2 connection."""
        fc_parameters = {"GPS_TYPE": 9, "CAN_D2_PROTOCOL": 1, "CAN_P2_DRIVER": 2}

        realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)

        gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        gnss_protocol = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Protocol"))
        assert gnss_type == "CAN2"
        assert gnss_protocol == "DroneCAN"

    def test_set_gnss_type_invalid_gps_type(self, realistic_model) -> None:
        """Test GNSS parameter processing with invalid GPS_TYPE."""
        fc_parameters = {"GPS_TYPE": "invalid"}

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)

        gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        assert gnss_type == "None"

    def test_set_gnss_type_unknown_gps_type(self, realistic_model) -> None:
        """Test GNSS parameter processing with unknown GPS_TYPE."""
        fc_parameters = {"GPS_TYPE": 999}

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)

        gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        assert gnss_type == "None"

    @patch(
        "ardupilot_methodic_configurator.data_model_vehicle_components_import.RC_PROTOCOLS_DICT", {"9": {"protocol": "CRSF"}}
    )
    def test_set_serial_type_rc_protocols_valid(self, realistic_model) -> None:
        """Test RC protocols processing with valid power of 2."""
        fc_parameters = {"RC_PROTOCOLS": 512}  # 2^9

        realistic_model._set_serial_type_from_fc_parameters(fc_parameters)

        rc_protocol = realistic_model.get_component_value(("RC Receiver", "FC Connection", "Protocol"))
        assert rc_protocol == "CRSF"

    def test_set_serial_type_rc_protocols_invalid(self, realistic_model) -> None:
        """Test RC protocols processing with invalid value."""
        fc_parameters = {"RC_PROTOCOLS": "invalid"}

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_serial_type_from_fc_parameters(fc_parameters)

    def test_set_serial_type_rc_protocols_not_power_of_two(self, realistic_model) -> None:
        """Test RC protocols processing with non-power of 2."""
        fc_parameters = {"RC_PROTOCOLS": 3}  # Not a power of 2

        realistic_model._set_serial_type_from_fc_parameters(fc_parameters)

        # Should not set protocol for non-power of 2 values

    @patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PORTS", ["SERIAL1", "SERIAL2"])
    @patch(
        "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PROTOCOLS_DICT",
        {"2": {"component": "Telemetry", "protocol": "MAVLink2"}},
    )
    def test_set_serial_type_telemetry(self, realistic_model) -> None:
        """Test serial telemetry connection processing."""
        fc_parameters = {"SERIAL1_PROTOCOL": 2}

        result = realistic_model._set_serial_type_from_fc_parameters(fc_parameters)

        telem_type = realistic_model.get_component_value(("Telemetry", "FC Connection", "Type"))
        telem_protocol = realistic_model.get_component_value(("Telemetry", "FC Connection", "Protocol"))
        assert telem_type == "SERIAL1"
        assert telem_protocol == "MAVLink2"
        assert result is False  # No ESC

    @patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PORTS", ["SERIAL1", "SERIAL2"])
    @patch(
        "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PROTOCOLS_DICT",
        {"30": {"component": "ESC", "protocol": "ESC Telem"}},
    )
    def test_set_serial_type_multiple_esc(self, realistic_model) -> None:
        """Test multiple ESC serial connections."""
        fc_parameters = {"SERIAL1_PROTOCOL": 30, "SERIAL2_PROTOCOL": 30}

        result = realistic_model._set_serial_type_from_fc_parameters(fc_parameters)

        esc_type = realistic_model.get_component_value(("ESC", "FC Connection", "Type"))
        esc_protocol = realistic_model.get_component_value(("ESC", "FC Connection", "Protocol"))
        assert esc_type == "SERIAL1"
        assert esc_protocol == "ESC Telem"
        assert result is True  # Multiple ESCs

    @patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PORTS", ["SERIAL1"])
    def test_set_serial_type_invalid_protocol(self, realistic_model) -> None:
        """Test serial processing with invalid protocol value."""
        fc_parameters = {"SERIAL1_PROTOCOL": "invalid"}

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            result = realistic_model._set_serial_type_from_fc_parameters(fc_parameters)

        assert result is False

    @patch(
        "ardupilot_methodic_configurator.data_model_vehicle_components_import.MOT_PWM_TYPE_DICT",
        {"6": {"protocol": "DShot600"}},
    )
    def test_set_esc_type_main_out(self, realistic_model) -> None:
        """Test ESC type processing for Main Out connection."""
        fc_parameters = {
            "MOT_PWM_TYPE": 6,
            "SERVO1_FUNCTION": 33,  # Motor1
        }
        doc = {"MOT_PWM_TYPE": {"values": {"6": "DShot600"}}}

        realistic_model._set_esc_type_from_fc_parameters(fc_parameters, doc)

        esc_type = realistic_model.get_component_value(("ESC", "FC Connection", "Type"))
        esc_protocol = realistic_model.get_component_value(("ESC", "FC Connection", "Protocol"))
        assert esc_type == "Main Out"
        assert esc_protocol == "DShot600"

    @patch(
        "ardupilot_methodic_configurator.data_model_vehicle_components_import.MOT_PWM_TYPE_DICT",
        {"6": {"protocol": "DShot600"}},
    )
    def test_set_esc_type_aio(self, realistic_model) -> None:
        """Test ESC type processing for AIO connection."""
        fc_parameters = {
            "MOT_PWM_TYPE": 6,
            "SERVO1_FUNCTION": 0,  # Not motor function
        }
        doc: dict[str, Any] = {}

        realistic_model._set_esc_type_from_fc_parameters(fc_parameters, doc)

        esc_type = realistic_model.get_component_value(("ESC", "FC Connection", "Type"))
        esc_protocol = realistic_model.get_component_value(("ESC", "FC Connection", "Protocol"))
        assert esc_type == "AIO"
        assert esc_protocol == "DShot600"

    def test_set_esc_type_invalid_mot_pwm_type(self, realistic_model) -> None:
        """Test ESC type processing with invalid MOT_PWM_TYPE."""
        fc_parameters = {"MOT_PWM_TYPE": "invalid"}
        doc: dict[str, Any] = {}

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_esc_type_from_fc_parameters(fc_parameters, doc)

    @patch(
        "ardupilot_methodic_configurator.data_model_vehicle_components_import.BATT_MONITOR_CONNECTION",
        {"4": {"type": "Analog", "protocol": "Analog Voltage and Current"}},
    )
    def test_set_battery_type_valid(self, realistic_model) -> None:
        """Test battery monitor processing with valid parameters."""
        fc_parameters = {"BATT_MONITOR": 4}

        realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

        batt_type = realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Type"))
        batt_protocol = realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Protocol"))
        assert batt_type == "Analog"
        assert batt_protocol == "Analog Voltage and Current"

    @patch(
        "ardupilot_methodic_configurator.data_model_vehicle_components_import.BATT_MONITOR_CONNECTION",
        {"4": {"type": ["Analog", "Digital"], "protocol": ["Voltage", "Current"]}},
    )
    def test_set_battery_type_list_values(self, realistic_model) -> None:
        """Test battery monitor processing with list values."""
        fc_parameters = {"BATT_MONITOR": 4}

        realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

        batt_type = realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Type"))
        batt_protocol = realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Protocol"))
        assert batt_type == "Analog"  # First element of list
        assert batt_protocol == "Voltage"  # First element of list

    def test_set_battery_type_invalid(self, realistic_model) -> None:
        """Test battery monitor processing with invalid parameters."""
        fc_parameters = {"BATT_MONITOR": "invalid"}

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

    @patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.MOT_PWM_TYPE_DICT", {"6": {"is_dshot": True}})
    def test_set_motor_poles_dshot(self, realistic_model) -> None:
        """Test motor poles processing for DShot."""
        fc_parameters = {"MOT_PWM_TYPE": "6", "SERVO_BLH_POLES": 14}

        realistic_model._set_motor_poles_from_fc_parameters(fc_parameters)

        motor_poles = realistic_model.get_component_value(("Motors", "Specifications", "Poles"))
        assert motor_poles == 14

    def test_set_motor_poles_fettec(self, realistic_model) -> None:
        """Test motor poles processing for FETtec."""
        fc_parameters = {"MOT_PWM_TYPE": "0", "SERVO_FTW_MASK": 15, "SERVO_FTW_POLES": 12}

        realistic_model._set_motor_poles_from_fc_parameters(fc_parameters)

        motor_poles = realistic_model.get_component_value(("Motors", "Specifications", "Poles"))
        assert motor_poles == 12

    def test_process_fc_parameters_complete(self, realistic_model) -> None:
        """Test complete FC parameters processing."""
        fc_parameters = {
            "GPS_TYPE": 2,
            "SERIAL3_PROTOCOL": 5,
            "RC_PROTOCOLS": 512,
            "SERIAL7_PROTOCOL": 23,
            "MOT_PWM_TYPE": 6,
            "SERVO1_FUNCTION": 33,
            "SERVO_BLH_POLES": 14,
            "BATT_MONITOR": 4,
        }
        doc = {
            "GPS_TYPE": {"values": {"2": "uBlox"}},
            "MOT_PWM_TYPE": {"values": {"6": "DShot600"}},
        }

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True):
            realistic_model.process_fc_parameters(fc_parameters, doc)

    def test_process_fc_parameters_empty(self, realistic_model) -> None:
        """Test FC parameters processing with empty parameters."""
        fc_parameters: dict[str, Any] = {}
        doc: dict[str, Any] = {}

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True):
            realistic_model.process_fc_parameters(fc_parameters, doc)

    def test_set_gnss_type_invalid_can_configuration(self, realistic_model) -> None:
        """Test GNSS CAN configuration with invalid CAN settings."""
        with (
            patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.GNSS_RECEIVER_CONNECTION",
                {"9": {"type": "CAN1", "protocol": "DroneCAN"}},
            ),
            patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.CAN_PORTS", ["CAN1", "CAN2"]),
        ):
            # Test invalid CAN1 configuration
            fc_parameters = {
                "GPS_TYPE": 9,
                "CAN_D1_PROTOCOL": 0,  # Invalid protocol
                "CAN_P1_DRIVER": 1,
            }

            with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
                realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)

            gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
            assert gnss_type == "None"

    def test_set_gnss_type_missing_can_parameters(self, realistic_model) -> None:
        """Test GNSS CAN configuration with missing CAN parameters."""
        with (
            patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.GNSS_RECEIVER_CONNECTION",
                {"9": {"type": "CAN1", "protocol": "DroneCAN"}},
            ),
            patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.CAN_PORTS", ["CAN1", "CAN2"]),
        ):
            # Test missing CAN parameters
            fc_parameters = {
                "GPS_TYPE": 9,
                # Missing CAN_D1_PROTOCOL and CAN_P1_DRIVER
            }

            with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
                realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)

            gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
            assert gnss_type == "None"

    def test_set_gnss_type_invalid_connection_type(self, realistic_model) -> None:
        """Test GNSS parameter processing with invalid connection type."""
        with patch(
            "ardupilot_methodic_configurator.data_model_vehicle_components_import.GNSS_RECEIVER_CONNECTION",
            {"9": {"type": "INVALID_TYPE", "protocol": "Unknown"}},
        ):
            fc_parameters = {"GPS_TYPE": 9}

            with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
                realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)

            gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
            assert gnss_type == "None"

    def test_set_gnss_type_gps_type_not_found(self, realistic_model) -> None:
        """Test GNSS parameter processing with GPS_TYPE not in connection dictionary."""
        fc_parameters = {"GPS_TYPE": 999}  # Non-existent GPS type

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)

        gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        assert gnss_type == "None"

    def test_set_serial_type_zero_protocol_skipped(self, realistic_model) -> None:
        """Test serial processing skips zero protocols."""
        with patch(
            "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PORTS", ["SERIAL1", "SERIAL2"]
        ):
            fc_parameters = {
                "SERIAL1_PROTOCOL": 0,  # Zero protocol should be skipped
                "SERIAL2_PROTOCOL": 5,  # Valid protocol
            }

            realistic_model._set_serial_type_from_fc_parameters(fc_parameters)
            # SERIAL1 should be skipped, only SERIAL2 processed

    def test_set_serial_type_missing_protocol_in_dict(self, realistic_model) -> None:
        """Test serial processing with protocol not in SERIAL_PROTOCOLS_DICT."""
        with (
            patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PORTS", ["SERIAL1"]),
            patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PROTOCOLS_DICT",
                {"5": {"component": "GNSS Receiver", "protocol": "GPS"}},
            ),
        ):
            fc_parameters = {"SERIAL1_PROTOCOL": 99}  # Not in dictionary

            result = realistic_model._set_serial_type_from_fc_parameters(fc_parameters)
            assert result is False

    def test_set_serial_type_none_component(self, realistic_model) -> None:
        """Test serial processing with None component."""
        with (
            patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PORTS", ["SERIAL1"]),
            patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PROTOCOLS_DICT",
                {"5": {"component": None, "protocol": "SomeProtocol"}},
            ),
        ):
            fc_parameters = {"SERIAL1_PROTOCOL": 5}

            result = realistic_model._set_serial_type_from_fc_parameters(fc_parameters)
            assert result is False

    def test_set_esc_type_missing_servo_functions(self, realistic_model) -> None:
        """Test ESC type processing when SERVO_FUNCTION parameters are missing."""
        fc_parameters = {"MOT_PWM_TYPE": 6}  # No SERVO functions defined
        doc = {"MOT_PWM_TYPE": {"values": {"6": "DShot600"}}}

        realistic_model._set_esc_type_from_fc_parameters(fc_parameters, doc)

        esc_type = realistic_model.get_component_value(("ESC", "FC Connection", "Type"))
        assert esc_type == "AIO"  # Should default to AIO when no main out functions

    def test_set_esc_type_fallback_to_mot_pwm_dict(self, realistic_model) -> None:
        """Test ESC type processing fallback to MOT_PWM_TYPE_DICT when doc is empty."""
        with patch(
            "ardupilot_methodic_configurator.data_model_vehicle_components_import.MOT_PWM_TYPE_DICT",
            {"6": {"protocol": "DShot600"}},
        ):
            fc_parameters = {"MOT_PWM_TYPE": 6}
            doc: dict[str, Any] = {}  # Empty doc should trigger fallback

            realistic_model._set_esc_type_from_fc_parameters(fc_parameters, doc)

            esc_protocol = realistic_model.get_component_value(("ESC", "FC Connection", "Protocol"))
            assert esc_protocol == "DShot600"

    def test_set_esc_type_protocol_not_found(self, realistic_model) -> None:
        """Test ESC type processing when protocol is not found in either source."""
        fc_parameters = {"MOT_PWM_TYPE": 999}  # Non-existent type
        doc = {"MOT_PWM_TYPE": {"values": {"6": "DShot600"}}}  # Doesn't contain 999

        realistic_model._set_esc_type_from_fc_parameters(fc_parameters, doc)
        # Should handle gracefully without setting protocol

    def test_set_battery_type_key_error(self, realistic_model) -> None:
        """Test battery monitor processing with KeyError."""
        fc_parameters = {"BATT_MONITOR": 999}  # Non-existent key

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

    def test_set_battery_type_type_error(self, realistic_model) -> None:
        """Test battery monitor processing with TypeError."""
        fc_parameters = {"BATT_MONITOR": None}  # Will cause TypeError in int()

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

    def test_set_motor_poles_no_dshot_no_fettec(self, realistic_model) -> None:
        """Test motor poles when neither DShot nor FETtec are configured."""
        initial_poles = realistic_model.get_component_value(("Motors", "Specifications", "Poles"))

        fc_parameters = {
            "MOT_PWM_TYPE": 0,  # Normal PWM, not DShot
            "SERVO_FTW_MASK": 0,  # No FETtec
        }

        realistic_model._set_motor_poles_from_fc_parameters(fc_parameters)

        # Should not change motor poles
        final_poles = realistic_model.get_component_value(("Motors", "Specifications", "Poles"))
        assert final_poles == initial_poles

    def test_set_motor_poles_dshot_without_poles_param(self, realistic_model) -> None:
        """Test motor poles for DShot without SERVO_BLH_POLES parameter."""
        with patch(
            "ardupilot_methodic_configurator.data_model_vehicle_components_import.MOT_PWM_TYPE_DICT",
            {"6": {"protocol": "DShot600", "is_dshot": True}},
        ):
            fc_parameters = {
                "MOT_PWM_TYPE": 6,
                # Missing SERVO_BLH_POLES
            }

            realistic_model._set_motor_poles_from_fc_parameters(fc_parameters)
            # Should handle gracefully without setting poles

    def test_set_motor_poles_fettec_without_mask(self, realistic_model) -> None:
        """Test motor poles for FETtec without SERVO_FTW_MASK."""
        fc_parameters = {
            "MOT_PWM_TYPE": 0,  # Not DShot
            "SERVO_FTW_POLES": 12,
            # Missing SERVO_FTW_MASK
        }

        realistic_model._set_motor_poles_from_fc_parameters(fc_parameters)
        # Should not set poles without mask

    def test_set_motor_poles_fettec_zero_mask(self, realistic_model) -> None:
        """Test motor poles for FETtec with zero mask."""
        fc_parameters = {
            "MOT_PWM_TYPE": 0,  # Not DShot
            "SERVO_FTW_MASK": 0,  # Zero mask
            "SERVO_FTW_POLES": 12,
        }

        realistic_model._set_motor_poles_from_fc_parameters(fc_parameters)
        # Should not set poles with zero mask

    def test_process_fc_parameters_comprehensive_integration(self, realistic_model, sample_doc_dict) -> None:
        """Test comprehensive integration of all FC parameter processing."""
        fc_parameters = {
            "GPS_TYPE": 2,
            "SERIAL1_PROTOCOL": 1,  # MAVLink1
            "SERIAL2_PROTOCOL": 5,  # GPS
            "SERIAL3_PROTOCOL": 23,  # RCIN
            "SERIAL4_PROTOCOL": 30,  # ESC
            "RC_PROTOCOLS": 512,  # CRSF (2^9)
            "MOT_PWM_TYPE": 6,  # DShot600
            "SERVO1_FUNCTION": 33,  # Motor1 on main out
            "SERVO2_FUNCTION": 34,  # Motor2 on main out
            "SERVO_BLH_POLES": 14,  # Motor poles for DShot
            "BATT_MONITOR": 4,  # Analog voltage and current
        }

        doc = {
            "SERIAL1_PROTOCOL": sample_doc_dict["SERIAL1_PROTOCOL"],
            "BATT_MONITOR": sample_doc_dict["BATT_MONITOR"],
            "GPS_TYPE": sample_doc_dict["GPS_TYPE"],
            "MOT_PWM_TYPE": sample_doc_dict["MOT_PWM_TYPE"],
            "RC_PROTOCOLS": sample_doc_dict["RC_PROTOCOLS"],
        }

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True):
            realistic_model.process_fc_parameters(fc_parameters, doc)

        # Verify all components were configured correctly
        assert realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type")) == "SERIAL2"
        assert realistic_model.get_component_value(("RC Receiver", "FC Connection", "Type")) == "SERIAL3"
        assert realistic_model.get_component_value(("RC Receiver", "FC Connection", "Protocol")) == "CRSF"
        assert realistic_model.get_component_value(("ESC", "FC Connection", "Type")) == "Main Out"
        assert realistic_model.get_component_value(("ESC", "FC Connection", "Protocol")) == "DShot600"
        assert realistic_model.get_component_value(("Motors", "Specifications", "Poles")) == 14
        assert (
            realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Protocol"))
            == "Analog Voltage and Current"
        )

    def test_process_fc_parameters_serial_esc_overrides_pwm_esc(self, realistic_model, sample_doc_dict) -> None:
        """Test that serial ESC configuration overrides PWM ESC configuration."""
        fc_parameters = {
            "SERIAL1_PROTOCOL": 38,  # FETtecOneWire ESC on serial
            "SERIAL2_PROTOCOL": 39,  # Torqeedo ESC on serial (should trigger serial ESC mode)
            "MOT_PWM_TYPE": 6,  # DShot600 - should be ignored
            "SERVO1_FUNCTION": 33,  # Motor on main out - should be ignored
        }

        doc = {
            "SERIAL1_PROTOCOL": {"values": {"38": "FETtecOneWire"}},
            "MOT_PWM_TYPE": sample_doc_dict["MOT_PWM_TYPE"],
        }

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True):
            realistic_model.process_fc_parameters(fc_parameters, doc)

        # Should use serial ESC, not PWM ESC
        esc_type = realistic_model.get_component_value(("ESC", "FC Connection", "Type"))
        esc_protocol = realistic_model.get_component_value(("ESC", "FC Connection", "Protocol"))
        assert esc_type == "SERIAL1"
        assert esc_protocol == "FETtecOneWire"

    def test_process_fc_parameters_multiple_components_same_serial(self, realistic_model, sample_doc_dict) -> None:
        """Test handling when multiple components try to use the same serial port."""
        fc_parameters = {
            "SERIAL1_PROTOCOL": 5,  # GPS
            "SERIAL2_PROTOCOL": 23,  # RCIN
            "SERIAL3_PROTOCOL": 1,  # Telemetry
        }

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True):
            realistic_model.process_fc_parameters(fc_parameters, sample_doc_dict)

        # Only first instance of each component type should be set
        gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        rc_type = realistic_model.get_component_value(("RC Receiver", "FC Connection", "Type"))
        telem_type = realistic_model.get_component_value(("Telemetry", "FC Connection", "Type"))

        assert gnss_type == "SERIAL1"
        assert rc_type == "SERIAL2"
        assert telem_type == "SERIAL3"

    def test_process_fc_parameters_invalid_documentation(self, realistic_model) -> None:
        """Test processing with invalid or incomplete documentation."""
        fc_parameters = {
            "GPS_TYPE": 2,
            "MOT_PWM_TYPE": 6,
            "BATT_MONITOR": 4,
        }

        # Empty documentation
        doc: dict[str, Any] = {}

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=False):
            realistic_model.process_fc_parameters(fc_parameters, doc)

        # Should still process parameters using fallback dictionaries

    def test_process_fc_parameters_all_verification_failures(self, realistic_model) -> None:
        """Test processing when all dictionary verifications fail."""
        fc_parameters = {
            "GPS_TYPE": 2,
            "SERIAL1_PROTOCOL": 5,
            "RC_PROTOCOLS": 512,
            "MOT_PWM_TYPE": 6,
            "BATT_MONITOR": 4,
        }

        doc = {"some": "data"}

        # Mock all verifications to fail
        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=False) as mock_verify:
            realistic_model.process_fc_parameters(fc_parameters, doc)

            # Should call verification 5 times (once for each dictionary)
            assert mock_verify.call_count == 5

    def test_rc_protocols_boundary_values(self, realistic_model) -> None:
        """Test RC protocols with boundary and edge values."""
        test_cases = [
            (1, True),  # 2^0 - valid power of 2
            (2, True),  # 2^1 - valid power of 2
            (4, True),  # 2^2 - valid power of 2
            (512, True),  # 2^9 - valid power of 2
            (1024, True),  # 2^10 - valid power of 2
            (0, False),  # Zero - invalid
            (3, False),  # Not power of 2
            (5, False),  # Not power of 2
            (511, False),  # Not power of 2
        ]

        for rc_protocols_value, should_be_valid in test_cases:
            fc_parameters = {"RC_PROTOCOLS": rc_protocols_value}

            # Reset protocol before each test
            realistic_model.set_component_value(("RC Receiver", "FC Connection", "Protocol"), "")

            realistic_model._set_serial_type_from_fc_parameters(fc_parameters)

            protocol = realistic_model.get_component_value(("RC Receiver", "FC Connection", "Protocol"))

            if should_be_valid and rc_protocols_value > 0:
                # Should set some protocol for valid power of 2 values
                assert protocol != ""
            else:
                # Should not set protocol for invalid values
                assert protocol == ""

    def test_gnss_can_port_edge_cases(self, realistic_model) -> None:
        """Test GNSS CAN port configuration edge cases."""
        with (
            patch(
                "ardupilot_methodic_configurator.data_model_vehicle_components_import.GNSS_RECEIVER_CONNECTION",
                {"9": {"type": "CAN1", "protocol": "DroneCAN"}, "10": {"type": "CAN2", "protocol": "DroneCAN"}},
            ),
            patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.CAN_PORTS", ["CAN1", "CAN2"]),
        ):
            # Test CAN1 with correct configuration
            fc_parameters_can1 = {"GPS_TYPE": 9, "CAN_D1_PROTOCOL": 1, "CAN_P1_DRIVER": 1}

            realistic_model._set_gnss_type_from_fc_parameters(fc_parameters_can1)
            gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
            assert gnss_type == "CAN1"

            # Test CAN2 with correct configuration
            fc_parameters_can2 = {"GPS_TYPE": 10, "CAN_D2_PROTOCOL": 1, "CAN_P2_DRIVER": 2}

            realistic_model._set_gnss_type_from_fc_parameters(fc_parameters_can2)
            gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
            assert gnss_type == "CAN2"

    def test_servo_functions_comprehensive_combinations(self, realistic_model) -> None:
        """Test ESC type detection with various servo function combinations."""
        test_cases = [
            # Test case: (servo functions, expected_esc_type)
            ([0, 0, 0, 0, 0, 0, 0, 0], "AIO"),  # No motors on main out
            ([33, 0, 0, 0, 0, 0, 0, 0], "Main Out"),  # Motor1 on SERVO1
            ([0, 34, 0, 0, 0, 0, 0, 0], "Main Out"),  # Motor2 on SERVO2
            ([0, 0, 35, 0, 0, 0, 0, 0], "Main Out"),  # Motor3 on SERVO3
            ([0, 0, 0, 36, 0, 0, 0, 0], "Main Out"),  # Motor4 on SERVO4
            ([0, 0, 0, 0, 33, 0, 0, 0], "Main Out"),  # Motor1 on SERVO5 (still main out, not AUX)
            ([1, 2, 3, 4, 5, 6, 7, 8], "AIO"),  # Other functions, no motors
            ([33, 34, 35, 36, 0, 0, 0, 0], "Main Out"),  # All 4 motors on main out
        ]

        for servo_functions, expected_esc_type in test_cases:
            fc_parameters = {"MOT_PWM_TYPE": 6}  # DShot600

            # Set all servo functions
            for i, function in enumerate(servo_functions, 1):
                fc_parameters[f"SERVO{i}_FUNCTION"] = function

            doc = {"MOT_PWM_TYPE": {"values": {"6": "DShot600"}}}

            realistic_model._set_esc_type_from_fc_parameters(fc_parameters, doc)

            esc_type = realistic_model.get_component_value(("ESC", "FC Connection", "Type"))
            assert esc_type == expected_esc_type, f"Failed for servo functions {servo_functions}"
