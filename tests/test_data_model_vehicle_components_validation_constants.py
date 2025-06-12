#!/usr/bin/env python3

"""
Tests for vehicle components validation constants.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest

from ardupilot_methodic_configurator.data_model_vehicle_components_validation import (
    ANALOG_PORTS,
    BATT_MONITOR_CONNECTION,
    BATTERY_CELL_VOLTAGE_PATHS,
    CAN_PORTS,
    FC_CONNECTION_TYPE_PATHS,
    GNSS_RECEIVER_CONNECTION,
    I2C_PORTS,
    MOT_PWM_TYPE_DICT,
    OTHER_PORTS,
    PWM_IN_PORTS,
    PWM_OUT_PORTS,
    RC_PORTS,
    RC_PROTOCOLS_DICT,
    SERIAL_PORTS,
    SERIAL_PROTOCOLS_DICT,
    SPI_PORTS,
)


class TestValidationConstants:
    """Test the structure and data types of validation constants."""

    def test_fc_connection_type_paths_structure(self) -> None:
        """Test FC_CONNECTION_TYPE_PATHS structure and data types."""
        # Should be a list
        assert isinstance(FC_CONNECTION_TYPE_PATHS, list)
        assert len(FC_CONNECTION_TYPE_PATHS) > 0

        # Each item should be a tuple with exactly 3 string elements
        for path in FC_CONNECTION_TYPE_PATHS:
            assert isinstance(path, tuple)
            assert len(path) == 3
            assert all(isinstance(element, str) for element in path)

        # All paths should follow the pattern (Component, "FC Connection", "Type")
        for path in FC_CONNECTION_TYPE_PATHS:
            assert path[1] == "FC Connection"
            assert path[2] == "Type"

    def test_battery_cell_voltage_paths_structure(self) -> None:
        """Test BATTERY_CELL_VOLTAGE_PATHS structure and data types."""
        # Should be a list
        assert isinstance(BATTERY_CELL_VOLTAGE_PATHS, list)
        assert len(BATTERY_CELL_VOLTAGE_PATHS) > 0

        # Each item should be a tuple with exactly 3 string elements
        for path in BATTERY_CELL_VOLTAGE_PATHS:
            assert isinstance(path, tuple)
            assert len(path) == 3
            assert all(isinstance(element, str) for element in path)

        # Verify specific required paths exist
        expected_paths = [
            ("Battery", "Specifications", "Volt per cell max"),
            ("Battery", "Specifications", "Volt per cell low"),
            ("Battery", "Specifications", "Volt per cell crit"),
        ]

        for expected_path in expected_paths:
            assert expected_path in BATTERY_CELL_VOLTAGE_PATHS

        # All paths should follow the pattern ("Battery", "Specifications", "Volt per cell XXX")
        for path in BATTERY_CELL_VOLTAGE_PATHS:
            assert path[0] == "Battery"
            assert path[1] == "Specifications"
            assert path[2].startswith("Volt per cell")

        # Should contain exactly the three expected voltage types
        assert len(BATTERY_CELL_VOLTAGE_PATHS) == 3

        # Verify that the expected voltage types are present
        voltage_types = {path[2] for path in BATTERY_CELL_VOLTAGE_PATHS}
        expected_voltage_types = {"Volt per cell max", "Volt per cell low", "Volt per cell crit"}
        assert voltage_types == expected_voltage_types

        # Should not have duplicates
        assert len(BATTERY_CELL_VOLTAGE_PATHS) == len(set(BATTERY_CELL_VOLTAGE_PATHS))

    def test_serial_protocols_dict_structure(self) -> None:
        """Test SERIAL_PROTOCOLS_DICT structure and data types."""
        # Should be a dict
        assert isinstance(SERIAL_PROTOCOLS_DICT, dict)
        assert len(SERIAL_PROTOCOLS_DICT) > 0

        # Keys should be strings representing protocol numbers
        for key in SERIAL_PROTOCOLS_DICT:
            assert isinstance(key, str)
            # Should be convertible to int (even if negative)
            try:
                int(key)
            except ValueError:
                pytest.fail(f"Key '{key}' is not a valid integer string")

        # Values should be dicts with specific structure
        required_fields = {"type", "protocol", "component"}
        for key, value in SERIAL_PROTOCOLS_DICT.items():
            assert isinstance(value, dict), f"Value for key '{key}' is not a dict"
            assert set(value.keys()) == required_fields, f"Value for key '{key}' missing required fields"

            # Check field types
            assert isinstance(value["type"], list), f"'type' field for key '{key}' is not a list"

            assert isinstance(value["protocol"], str), f"'protocol' field for key '{key}' is not a string"
            assert value["component"] is None or isinstance(value["component"], str), (
                f"'component' field for key '{key}' is not None or string"
            )

            # Type should reference known port lists or be specific port names
            type_list = value["type"]
            assert len(type_list) > 0, f"'type' field for key '{key}' is empty"

            # Each type should be a string
            for port_type in type_list:
                assert isinstance(port_type, str), f"Port type in key '{key}' is not a string"

            # Type should reference known port lists
            assert type_list in (SERIAL_PORTS, ["None"]), f"'type' field for key '{key}' does not reference SERIAL_PORTS"

        # Verify some expected protocols exist
        expected_protocols = {
            "1": "MAVLink1",
            "2": "MAVLink2",
            "5": "GPS",
            "23": "RCIN",
        }

        for key, protocol in expected_protocols.items():
            assert key in SERIAL_PROTOCOLS_DICT
            assert SERIAL_PROTOCOLS_DICT[key]["protocol"] == protocol

    def test_batt_monitor_connection_structure(self) -> None:
        """Test BATT_MONITOR_CONNECTION structure and data types."""
        # Should be a dict
        assert isinstance(BATT_MONITOR_CONNECTION, dict)
        assert len(BATT_MONITOR_CONNECTION) > 0

        # Keys should be strings representing monitor type numbers
        for key in BATT_MONITOR_CONNECTION:
            assert isinstance(key, str)
            # Should be convertible to int
            try:
                int(key)
            except ValueError:
                pytest.fail(f"Key '{key}' is not a valid integer string")

        # Values should be dicts with specific structure
        required_fields = {"type", "protocol"}
        for key, value in BATT_MONITOR_CONNECTION.items():
            assert isinstance(value, dict), f"Value for key '{key}' is not a dict"
            assert set(value.keys()) == required_fields, f"Value for key '{key}' has incorrect fields"

            # Check field types
            assert isinstance(value["type"], list), f"'type' field for key '{key}' is not a list"
            assert isinstance(value["protocol"], str), f"'protocol' field for key '{key}' is not a string"

            # Type should reference known port lists or be specific port names
            type_list = value["type"]
            assert len(type_list) > 0, f"'type' field for key '{key}' is empty"

            # Each type should be a string
            for port_type in type_list:
                assert isinstance(port_type, str), f"Port type in key '{key}' is not a string"

            # Verify type list references known port definitions
            known_port_lists = [
                ANALOG_PORTS,
                SERIAL_PORTS,
                CAN_PORTS,
                I2C_PORTS,
                PWM_IN_PORTS,
                PWM_OUT_PORTS,
                SPI_PORTS,
                OTHER_PORTS,
            ]

            # Type should either be one of the known port lists or contain valid port names
            if type_list not in known_port_lists:
                # If not a known port list, should contain strings from known ports
                all_known_ports = set()
                for port_list in known_port_lists:
                    all_known_ports.update(port_list)
                all_known_ports.add("None")  # Special case for disabled

                for port in type_list:
                    assert port in all_known_ports or port == "None", f"Unknown port '{port}' in key '{key}'"

        # Verify some expected monitor types exist
        expected_monitors = {
            "0": "Disabled",
            "4": "Analog Voltage and Current",
        }

        for key, protocol in expected_monitors.items():
            assert key in BATT_MONITOR_CONNECTION
            assert BATT_MONITOR_CONNECTION[key]["protocol"] == protocol

    def test_gnss_receiver_connection_structure(self) -> None:
        """Test GNSS_RECEIVER_CONNECTION structure and data types."""
        # Should be a dict
        assert isinstance(GNSS_RECEIVER_CONNECTION, dict)
        assert len(GNSS_RECEIVER_CONNECTION) > 0

        # Keys should be strings representing GPS type numbers
        for key in GNSS_RECEIVER_CONNECTION:
            assert isinstance(key, str)
            # Should be convertible to int
            try:
                int(key)
            except ValueError:
                pytest.fail(f"Key '{key}' is not a valid integer string")

        # Values should be dicts with specific structure
        required_fields = {"type", "protocol"}
        for key, value in GNSS_RECEIVER_CONNECTION.items():
            assert isinstance(value, dict), f"Value for key '{key}' is not a dict"
            assert set(value.keys()) == required_fields, f"Value for key '{key}' has incorrect fields"

            # Check field types
            assert isinstance(value["type"], list), f"'type' field for key '{key}' is not a list"
            assert isinstance(value["protocol"], str), f"'protocol' field for key '{key}' is not a string"

            # Type should reference known port lists or be specific port names
            type_list = value["type"]
            assert len(type_list) > 0, f"'type' field for key '{key}' is empty"

            # Each type should be a string
            for port_type in type_list:
                assert isinstance(port_type, str), f"Port type in key '{key}' is not a string"

            # Verify type list references known port definitions
            known_port_lists = [SERIAL_PORTS, CAN_PORTS]
            all_known_ports = set()
            for port_list in known_port_lists:
                all_known_ports.update(port_list)
            all_known_ports.add("None")  # Special case for disabled

            if type_list not in known_port_lists:
                for port in type_list:
                    assert port in all_known_ports or port == "None", f"Unknown port '{port}' in key '{key}'"

        # Verify some expected GPS types exist
        expected_gps_types = {
            "0": "None",
            "2": "uBlox",
        }

        for key, protocol in expected_gps_types.items():
            assert key in GNSS_RECEIVER_CONNECTION
            assert GNSS_RECEIVER_CONNECTION[key]["protocol"] == protocol

    def test_mot_pwm_type_dict_structure(self) -> None:
        """Test MOT_PWM_TYPE_DICT structure and data types."""
        # Should be a dict
        assert isinstance(MOT_PWM_TYPE_DICT, dict)
        assert len(MOT_PWM_TYPE_DICT) > 0

        # Keys should be strings representing PWM type numbers
        for key in MOT_PWM_TYPE_DICT:
            assert isinstance(key, str)
            # Should be convertible to int
            try:
                int(key)
            except ValueError:
                pytest.fail(f"Key '{key}' is not a valid integer string")

        # Values should be dicts with specific structure
        required_fields = {"type", "protocol", "is_dshot"}
        for key, value in MOT_PWM_TYPE_DICT.items():
            assert isinstance(value, dict), f"Value for key '{key}' is not a dict"
            assert set(value.keys()) == required_fields, f"Value for key '{key}' has incorrect fields"

            # Check field types
            assert isinstance(value["type"], list), f"'type' field for key '{key}' is not a list"
            assert isinstance(value["protocol"], str), f"'protocol' field for key '{key}' is not a string"
            assert isinstance(value["is_dshot"], bool), f"'is_dshot' field for key '{key}' is not a boolean"

            # Type should reference PWM output ports
            assert value["type"] == PWM_OUT_PORTS, f"'type' field for key '{key}' does not reference PWM_OUT_PORTS"

        # Verify some expected PWM types exist
        expected_pwm_types = {
            "0": {"protocol": "Normal", "is_dshot": False},
            "6": {"protocol": "DShot600", "is_dshot": True},
        }

        for key, expected_data in expected_pwm_types.items():
            assert key in MOT_PWM_TYPE_DICT
            assert MOT_PWM_TYPE_DICT[key]["protocol"] == expected_data["protocol"]
            assert MOT_PWM_TYPE_DICT[key]["is_dshot"] == expected_data["is_dshot"]

    def test_rc_protocols_dict_structure(self) -> None:
        """Test RC_PROTOCOLS_DICT structure and data types."""
        # Should be a dict
        assert isinstance(RC_PROTOCOLS_DICT, dict)
        assert len(RC_PROTOCOLS_DICT) > 0

        # Keys should be strings representing protocol bit numbers
        for key in RC_PROTOCOLS_DICT:
            assert isinstance(key, str)
            # Should be convertible to int
            try:
                int(key)
            except ValueError:
                pytest.fail(f"Key '{key}' is not a valid integer string")

        # Values should be dicts with specific structure
        required_fields = {"type", "protocol"}
        for key, value in RC_PROTOCOLS_DICT.items():
            assert isinstance(value, dict), f"Value for key '{key}' is not a dict"
            assert set(value.keys()) == required_fields, f"Value for key '{key}' has incorrect fields"

            # Check field types
            assert isinstance(value["type"], list), f"'type' field for key '{key}' is not a list"
            assert isinstance(value["protocol"], str), f"'protocol' field for key '{key}' is not a string"

            # Type should be combination of RC_PORTS + SERIAL_PORTS or CAN_PORTS
            type_list = value["type"]
            assert len(type_list) > 0, f"'type' field for key '{key}' is empty"

            # Each type should be a string
            for port_type in type_list:
                assert isinstance(port_type, str), f"Port type in key '{key}' is not a string"

            # Verify type list contains valid port references
            expected_rc_serial = RC_PORTS + SERIAL_PORTS
            if type_list == CAN_PORTS:
                # CAN protocols are valid
                pass
            elif set(type_list) <= set(expected_rc_serial):
                # RC + Serial combination is valid
                pass
            else:
                pytest.fail(f"Unexpected port combination in key '{key}': {type_list}")

        # Verify some expected RC protocols exist
        expected_rc_protocols = {
            "9": "CRSF",
            "11": "FPORT",
        }

        for key, protocol in expected_rc_protocols.items():
            assert key in RC_PROTOCOLS_DICT
            assert RC_PROTOCOLS_DICT[key]["protocol"] == protocol

    def test_port_definitions_consistency(self) -> None:
        """Test that port definitions are consistent and properly typed."""
        port_lists = [
            ("ANALOG_PORTS", ANALOG_PORTS),
            ("SERIAL_PORTS", SERIAL_PORTS),
            ("CAN_PORTS", CAN_PORTS),
            ("I2C_PORTS", I2C_PORTS),
            ("PWM_IN_PORTS", PWM_IN_PORTS),
            ("PWM_OUT_PORTS", PWM_OUT_PORTS),
            ("RC_PORTS", RC_PORTS),
            ("SPI_PORTS", SPI_PORTS),
            ("OTHER_PORTS", OTHER_PORTS),
        ]

        for port_name, port_list in port_lists:
            # Should be a list
            assert isinstance(port_list, list), f"{port_name} is not a list"

            # Should not be empty
            assert len(port_list) > 0, f"{port_name} is empty"

            # All items should be strings
            for port in port_list:
                assert isinstance(port, str), f"Port '{port}' in {port_name} is not a string"
                assert len(port) > 0, f"Empty port name in {port_name}"

            # Should not have duplicates
            assert len(port_list) == len(set(port_list)), f"{port_name} contains duplicates"

    def test_protocol_component_mapping_consistency(self) -> None:
        """Test that protocol component mappings are consistent."""
        # Collect all components mentioned in SERIAL_PROTOCOLS_DICT
        serial_components = set()
        for protocol_info in SERIAL_PROTOCOLS_DICT.values():
            if protocol_info["component"] is not None:
                serial_components.add(protocol_info["component"])

        # Verify that components mentioned in protocols exist in FC_CONNECTION_TYPE_PATHS
        fc_components = {path[0] for path in FC_CONNECTION_TYPE_PATHS}

        for component in serial_components:
            assert component in fc_components, (
                f"Component '{component}' referenced in SERIAL_PROTOCOLS_DICT but not in FC_CONNECTION_TYPE_PATHS"
            )

    def test_protocol_number_ranges(self) -> None:
        """Test that protocol numbers are within expected ranges."""
        # Serial protocol numbers should be reasonable (typically 0-50)
        for key in SERIAL_PROTOCOLS_DICT:
            protocol_num = int(key)
            assert -1 <= protocol_num <= 100, f"Serial protocol number {protocol_num} is out of expected range"

        # Battery monitor numbers should be reasonable (typically 0-30)
        for key in BATT_MONITOR_CONNECTION:
            monitor_num = int(key)
            assert 0 <= monitor_num <= 50, f"Battery monitor number {monitor_num} is out of expected range"

        # GPS type numbers should be reasonable (typically 0-30)
        for key in GNSS_RECEIVER_CONNECTION:
            gps_num = int(key)
            assert 0 <= gps_num <= 50, f"GPS type number {gps_num} is out of expected range"

        # Motor PWM type numbers should be reasonable (typically 0-10)
        for key in MOT_PWM_TYPE_DICT:
            pwm_num = int(key)
            assert 0 <= pwm_num <= 20, f"Motor PWM type number {pwm_num} is out of expected range"

        # RC protocol numbers should be reasonable bit positions (typically 0-15)
        for key in RC_PROTOCOLS_DICT:
            rc_num = int(key)
            assert 0 <= rc_num <= 20, f"RC protocol number {rc_num} is out of expected range"

    def test_protocol_names_not_empty(self) -> None:
        """Test that all protocol names are non-empty strings."""
        protocol_dicts = [
            ("SERIAL_PROTOCOLS_DICT", SERIAL_PROTOCOLS_DICT),
            ("BATT_MONITOR_CONNECTION", BATT_MONITOR_CONNECTION),
            ("GNSS_RECEIVER_CONNECTION", GNSS_RECEIVER_CONNECTION),
            ("MOT_PWM_TYPE_DICT", MOT_PWM_TYPE_DICT),
            ("RC_PROTOCOLS_DICT", RC_PROTOCOLS_DICT),
        ]

        for dict_name, protocol_dict in protocol_dicts:
            for key, value in protocol_dict.items():
                protocol_name = value["protocol"]
                assert isinstance(protocol_name, str), f"Protocol name for key '{key}' in {dict_name} is not a string"
                assert len(protocol_name.strip()) > 0, f"Protocol name for key '{key}' in {dict_name} is empty or whitespace"

    def test_no_protocol_duplicates_within_dict(self) -> None:
        """Test that there are no duplicate protocol names within each dictionary."""
        protocol_dicts = [
            ("SERIAL_PROTOCOLS_DICT", SERIAL_PROTOCOLS_DICT),
            ("BATT_MONITOR_CONNECTION", BATT_MONITOR_CONNECTION),
            ("GNSS_RECEIVER_CONNECTION", GNSS_RECEIVER_CONNECTION),
            ("MOT_PWM_TYPE_DICT", MOT_PWM_TYPE_DICT),
            ("RC_PROTOCOLS_DICT", RC_PROTOCOLS_DICT),
        ]

        for dict_name, protocol_dict in protocol_dicts:
            protocol_names = [value["protocol"] for value in protocol_dict.values()]
            unique_names = set(protocol_names)

            # Some protocols might legitimately have the same name (like "None"), so we allow some overlap
            # but check that it's reasonable
            assert len(unique_names) > 0, f"No protocols found in {dict_name}"

            # At least 80% of protocols should have unique names to catch major duplications
            uniqueness_ratio = len(unique_names) / len(protocol_names)
            assert uniqueness_ratio >= 0.8, (
                f"Too many duplicate protocol names in {dict_name}: {len(unique_names)}/{len(protocol_names)} unique"
            )
