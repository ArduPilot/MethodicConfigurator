#!/usr/bin/env python3

"""
Tests for vehicle components validation constants.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest

from ardupilot_methodic_configurator.data_model_vehicle_components_validation import (
    ANALOG_PORTS,
    BATT_MONITOR_CONNECTION,
    BATTERY_CELL_VOLTAGE_PATHS,
    BATTERY_CELL_VOLTAGE_TYPES,
    CAN_PORTS,
    ESC_CONNECTION_DICT,
    ESC_SERIAL_SAME_PORT_PROTOCOLS,
    FC_CONNECTION_TYPE_PATHS,
    FRAME_CLASS_DICT,
    GNSS_RECEIVER_CONNECTION,
    I2C_PORTS,
    OTHER_PORTS,
    PWM_IN_PORTS,
    PWM_OUT_PORTS,
    RC_PORTS,
    RC_PROTOCOLS_DICT,
    SERIAL_BUS_LABELS,
    SERIAL_PORTS,
    SERIAL_PROTOCOLS_DICT,
    SPI_PORTS,
    get_connection_type_tuples_with_labels,
    get_frame_class_as_protocol_dict,
    get_frame_class_valid_tuple,
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
            assert path[1] in [
                "FC Connection",
                "FC->ESC Connection",
                "ESC->FC Telemetry",
            ]
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

        # Verify specific required paths exist and use shared constants for maintainability
        expected_paths = [("Battery", "Specifications", vt) for vt in BATTERY_CELL_VOLTAGE_TYPES]

        for expected_path in expected_paths:
            assert expected_path in BATTERY_CELL_VOLTAGE_PATHS

        # All paths should follow the pattern ("Battery", "Specifications", "Volt per cell XXX")
        for path in BATTERY_CELL_VOLTAGE_PATHS:
            assert path[0] == "Battery"
            assert path[1] == "Specifications"
            assert path[2].startswith("Volt per cell")

        # Should contain exactly the five expected voltage types
        assert len(BATTERY_CELL_VOLTAGE_PATHS) == 5

        # Verify that the expected voltage types are present
        voltage_types = {path[2] for path in BATTERY_CELL_VOLTAGE_PATHS}
        assert voltage_types == set(BATTERY_CELL_VOLTAGE_TYPES)

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
            assert isinstance(value["type"], tuple), f"'type' field for key '{key}' is not a tuple"

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
            assert type_list in (SERIAL_PORTS, ("None",)), f"'type' field for key '{key}' does not reference SERIAL_PORTS"

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
            assert isinstance(value["type"], tuple), f"'type' field for key '{key}' is not a tuple"
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
            assert isinstance(value["type"], tuple), f"'type' field for key '{key}' is not a tuple"
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

    def test_esc_connection_dict_structure(self) -> None:
        """Test ESC_CONNECTION_DICT structure and data types (replaces deleted MOT_PWM_TYPE_DICT)."""
        # Should be a dict of vehicle-type sub-dicts
        assert isinstance(ESC_CONNECTION_DICT, dict)
        assert len(ESC_CONNECTION_DICT) > 0

        # Top-level keys are vehicle type strings (e.g. "ArduCopter", "Rover")
        for vtype, sub_dict in ESC_CONNECTION_DICT.items():
            assert isinstance(vtype, str), f"Vehicle type key '{vtype}' is not a string"
            assert isinstance(sub_dict, dict), f"Sub-dict for '{vtype}' is not a dict"

            # Inner keys should be integer strings representing protocol numbers
            for key in sub_dict:
                assert isinstance(key, str)
                try:
                    int(key)
                except ValueError:
                    pytest.fail(f"Key '{key}' in ESC_CONNECTION_DICT['{vtype}'] is not a valid integer string")

            # Values should be dicts with specific structure
            required_fields = {"type", "protocol", "ESC_to_FC"}
            for key, value in sub_dict.items():
                assert isinstance(value, dict), f"Value for key '{key}' in '{vtype}' is not a dict"
                assert set(value.keys()) == required_fields, f"Value for key '{key}' in '{vtype}' has incorrect fields"

                # Check field types
                assert isinstance(value["type"], tuple), f"'type' field for key '{key}' in '{vtype}' is not a tuple"
                assert isinstance(value["protocol"], str), f"'protocol' field for key '{key}' in '{vtype}' is not a string"
                assert isinstance(value["ESC_to_FC"], dict), f"'ESC_to_FC' field for key '{key}' in '{vtype}' is not a dict"

        # Verify expected PWM types exist in the ArduCopter sub-dict
        copter_sub = ESC_CONNECTION_DICT["ArduCopter"]
        assert "0" in copter_sub
        assert copter_sub["0"]["protocol"] == "Normal"
        assert "6" in copter_sub
        assert copter_sub["6"]["protocol"] == "DShot600"

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
            assert isinstance(value["type"], tuple), f"'type' field for key '{key}' is not a tuple"
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

        # Verify some expected RC protocols exist (using bitmask values, not bit positions)
        expected_rc_protocols = {
            "512": "CRSF",  # Bit 9 -> 2^9 = 512
            "2048": "FPORT",  # Bit 11 -> 2^11 = 2048
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
            # Should be a tuple (constants use tuple for immutability)
            assert isinstance(port_list, tuple), f"{port_name} is not a tuple"

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

        # Motor PWM type numbers should be reasonable (typically -1 to 200)
        for sub_dict in ESC_CONNECTION_DICT.values():
            for key in sub_dict:
                pwm_num = int(key)
                assert -1 <= pwm_num <= 200, f"ESC connection key {pwm_num} is out of expected range"

        # RC protocol numbers should be reasonable bit positions (typically 0-15)
        for key in RC_PROTOCOLS_DICT:
            rc_num = int(key)
            assert 1 <= rc_num <= 65536, f"RC protocol number {rc_num} is out of expected range (bitmask values)"

    def test_protocol_names_not_empty(self) -> None:
        """Test that all protocol names are non-empty strings."""
        protocol_dicts = [
            ("SERIAL_PROTOCOLS_DICT", SERIAL_PROTOCOLS_DICT),
            ("BATT_MONITOR_CONNECTION", BATT_MONITOR_CONNECTION),
            ("GNSS_RECEIVER_CONNECTION", GNSS_RECEIVER_CONNECTION),
            ("RC_PROTOCOLS_DICT", RC_PROTOCOLS_DICT),
        ]

        for dict_name, protocol_dict in protocol_dicts:
            for key, value in protocol_dict.items():
                protocol_name = value["protocol"]
                assert isinstance(protocol_name, str), f"Protocol name for key '{key}' in {dict_name} is not a string"
                assert len(protocol_name.strip()) > 0, f"Protocol name for key '{key}' in {dict_name} is empty or whitespace"

        for vtype, sub_dict in ESC_CONNECTION_DICT.items():
            for key, value in sub_dict.items():
                protocol_name = value["protocol"]
                assert isinstance(protocol_name, str), (
                    f"Protocol name for key '{key}' in ESC_CONNECTION_DICT['{vtype}'] is not a string"
                )
                assert len(protocol_name.strip()) > 0, (
                    f"Protocol name for key '{key}' in ESC_CONNECTION_DICT['{vtype}'] is empty"
                )

    def test_no_protocol_duplicates_within_dict(self) -> None:
        """Test that there are no duplicate protocol names within each dictionary."""
        protocol_dicts = [
            ("SERIAL_PROTOCOLS_DICT", SERIAL_PROTOCOLS_DICT),
            ("BATT_MONITOR_CONNECTION", BATT_MONITOR_CONNECTION),
            ("GNSS_RECEIVER_CONNECTION", GNSS_RECEIVER_CONNECTION),
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

        # Check uniqueness within each vehicle-type sub-dict of ESC_CONNECTION_DICT
        for vtype, sub_dict in ESC_CONNECTION_DICT.items():
            protocol_names = [value["protocol"] for value in sub_dict.values()]
            unique_names = set(protocol_names)
            assert len(unique_names) > 0, f"No protocols found in ESC_CONNECTION_DICT['{vtype}']"
            uniqueness_ratio = len(unique_names) / len(protocol_names)
            assert uniqueness_ratio >= 0.8, (
                f"Too many duplicate protocol names in ESC_CONNECTION_DICT['{vtype}']: "
                f"{len(unique_names)}/{len(protocol_names)} unique"
            )

    def test_serial_bus_labels_structure(self) -> None:
        """Test SERIAL_BUS_LABELS structure and data types."""
        # Should be a dictionary
        assert isinstance(SERIAL_BUS_LABELS, dict)

        # Should have 8 entries (one for each SERIAL port)
        assert len(SERIAL_BUS_LABELS) == 8

        # Keys should be SERIAL port names
        for port in SERIAL_PORTS:
            assert port in SERIAL_BUS_LABELS, f"Missing bus label for {port}"

        # Values should be strings
        for key, value in SERIAL_BUS_LABELS.items():
            assert isinstance(key, str), f"Key {key} is not a string"
            assert isinstance(value, str), f"Value {value} is not a string"

        # Check specific well-known mappings
        assert SERIAL_BUS_LABELS["SERIAL1"] == "Telem1 (SERIAL1)"
        assert SERIAL_BUS_LABELS["SERIAL2"] == "Telem2 (SERIAL2)"
        assert SERIAL_BUS_LABELS["SERIAL3"] == "GPS1 (SERIAL3)"
        assert SERIAL_BUS_LABELS["SERIAL4"] == "GPS2 (SERIAL4)"

    def test_get_connection_type_tuples_with_labels_function(self) -> None:
        """Test get_connection_type_tuples_with_labels function."""
        # Test with SERIAL ports
        result = get_connection_type_tuples_with_labels(("SERIAL1", "SERIAL3"))
        assert len(result) == 2
        assert result[0] == ("SERIAL1", "Telem1 (SERIAL1)")
        assert result[1] == ("SERIAL3", "GPS1 (SERIAL3)")

        # Test with non-SERIAL ports
        result = get_connection_type_tuples_with_labels(("CAN1", "I2C1"))
        assert len(result) == 2
        assert result[0] == ("CAN1", "CAN1")
        assert result[1] == ("I2C1", "I2C1")

        # Test with mixed ports
        result = get_connection_type_tuples_with_labels(("None", "SERIAL2", "CAN1"))
        assert len(result) == 3
        assert result[0] == ("None", "None")
        assert result[1] == ("SERIAL2", "Telem2 (SERIAL2)")
        assert result[2] == ("CAN1", "CAN1")

        # Test with empty tuple
        result = get_connection_type_tuples_with_labels(())
        assert not result

    def test_esc_serial_same_port_protocols_contents(self) -> None:
        """
        Assert the exact contents of ESC_SERIAL_SAME_PORT_PROTOCOLS.

        This guards against silent omissions when SERIAL_PROTOCOLS_DICT is extended
        without updating the 'component' annotation required for derivation.
        """
        expected = {"FETtecOneWire", "Torqeedo", "CoDevESC"}
        assert set(ESC_SERIAL_SAME_PORT_PROTOCOLS) == expected, (
            f"ESC_SERIAL_SAME_PORT_PROTOCOLS has changed: got {set(ESC_SERIAL_SAME_PORT_PROTOCOLS)!r}, "
            f"expected {expected!r}. Update this test and verify SERIAL_PROTOCOLS_DICT 'component' annotations."
        )
        # Verify all protocols in ESC_SERIAL_SAME_PORT_PROTOCOLS are present in every vehicle sub-dict
        # that supports serial ESC connections. ArduPlane (Q_M_PWM_TYPE) only supports PWM/DShot/CAN.
        vehicle_types_without_serial_esc = {"ArduPlane"}
        for vtype, sub_dict in ESC_CONNECTION_DICT.items():
            if vtype in vehicle_types_without_serial_esc:
                continue
            vehicle_protocols = {entry.get("protocol") for entry in sub_dict.values()}
            for protocol in ESC_SERIAL_SAME_PORT_PROTOCOLS:
                assert protocol in vehicle_protocols, (
                    f"Protocol '{protocol}' from ESC_SERIAL_SAME_PORT_PROTOCOLS not found in ESC_CONNECTION_DICT['{vtype}']"
                )


class TestFrameClassDict:
    """Tests for FRAME_CLASS_DICT and get_frame_class_as_protocol_dict."""

    def test_frame_class_dict_structure(self) -> None:
        """FRAME_CLASS_DICT is keyed by vehicle type with int->str sub-dicts."""
        assert isinstance(FRAME_CLASS_DICT, dict)
        assert len(FRAME_CLASS_DICT) > 0

        for vtype, sub_dict in FRAME_CLASS_DICT.items():
            assert isinstance(vtype, str), f"Vehicle type key '{vtype}' is not a string"
            assert isinstance(sub_dict, dict), f"Sub-dict for '{vtype}' is not a dict"
            for key, value in sub_dict.items():
                assert isinstance(key, int), f"Frame class key '{key}' in '{vtype}' is not an int"
                assert isinstance(value, str), f"Frame class value '{value}' in '{vtype}' is not a string"
                assert value.strip(), f"Frame class name for key {key} in '{vtype}' is empty"

    def test_frame_class_dict_contains_required_vehicle_types(self) -> None:
        """FRAME_CLASS_DICT contains entries for all expected vehicle types."""
        for required in ("ArduCopter", "Heli", "Rover", "ArduPlane"):
            assert required in FRAME_CLASS_DICT, f"Missing vehicle type '{required}' in FRAME_CLASS_DICT"

    def test_arducopter_frame_class_values(self) -> None:
        """ArduCopter sub-dict contains the standard multirotor frame classes."""
        sub = FRAME_CLASS_DICT["ArduCopter"]
        assert sub[1] == "Quad"
        assert sub[2] == "Hexa"
        assert sub[3] == "Octa"
        assert sub[6] == "Heli"
        assert sub[11] == "Heli_Dual"
        assert sub[13] == "HeliQuad"

    def test_heli_frame_class_values(self) -> None:
        """Heli sub-dict contains only helicopter-relevant frame classes."""
        sub = FRAME_CLASS_DICT["Heli"]
        assert sub[6] == "Heli"
        assert sub[11] == "Heli_Dual"
        assert sub[13] == "HeliQuad"
        # Non-heli classes must not appear
        assert 1 not in sub, "Quad should not be in Heli FRAME_CLASS_DICT"
        assert 2 not in sub, "Hexa should not be in Heli FRAME_CLASS_DICT"

    def test_heli_frame_class_includes_coax_and_single_variants(self) -> None:
        """Heli sub-dict includes newly added helicopter frame variants."""
        sub = FRAME_CLASS_DICT["Heli"]
        assert sub[0] == "Undefined"
        assert sub[8] == "SingleCopter"
        assert sub[9] == "CoaxCopter"
        assert sub[10] == "BiCopter"

    def test_rover_frame_class_values(self) -> None:
        """Rover sub-dict uses Rover-specific frame class values."""
        sub = FRAME_CLASS_DICT["Rover"]
        assert sub[1] == "Rover"
        assert sub[2] == "Boat"
        assert sub[3] == "BalanceBot"
        # Multirotor classes must not appear in Rover
        assert 4 not in sub, "OctaQuad should not be in Rover FRAME_CLASS_DICT"

    def test_arduplane_frame_class_values(self) -> None:
        """ArduPlane sub-dict contains plane-specific hover-capable frame classes."""
        sub = FRAME_CLASS_DICT["ArduPlane"]
        assert sub[1] == "Quad"
        assert sub[2] == "Hexa"
        assert sub[10] == "Single/Dual"
        assert sub[12] == "DodecaHexa"

    def test_get_frame_class_as_protocol_dict_known_vehicle_types(self) -> None:
        """get_frame_class_as_protocol_dict returns the correct protocol-shaped sub-dict for known vehicle types."""
        result = get_frame_class_as_protocol_dict("ArduCopter")
        assert result["1"] == {"protocol": "Quad"}
        assert result["2"] == {"protocol": "Hexa"}
        assert result["3"] == {"protocol": "Octa"}

        result = get_frame_class_as_protocol_dict("Heli")
        assert result["6"] == {"protocol": "Heli"}

        result = get_frame_class_as_protocol_dict("Rover")
        assert result["1"] == {"protocol": "Rover"}

        result = get_frame_class_as_protocol_dict("ArduPlane")
        assert result["1"] == {"protocol": "Quad"}

    def test_get_frame_class_as_protocol_dict_unknown_type_falls_back_to_arducopter(self) -> None:
        """get_frame_class_as_protocol_dict falls back to ArduCopter for unknown vehicle types."""
        result = get_frame_class_as_protocol_dict("UnknownVehicle")
        assert result["1"] == {"protocol": "Quad"}

    def test_get_frame_class_as_protocol_dict_empty_string_falls_back_to_arducopter(self) -> None:
        """get_frame_class_as_protocol_dict falls back to ArduCopter when fw_type is empty."""
        result = get_frame_class_as_protocol_dict("")
        assert result["1"] == {"protocol": "Quad"}

    def test_frame_class_values_are_unique_per_vehicle_type(self) -> None:
        """Within each vehicle type, frame class names must be unique."""
        for vtype, sub_dict in FRAME_CLASS_DICT.items():
            if not sub_dict:
                continue
            names = list(sub_dict.values())
            assert len(names) == len(set(names)), f"Duplicate frame class names found in '{vtype}'"

    def test_get_frame_class_valid_tuple_excludes_undefined_for_all_vehicle_types(self) -> None:
        """
        get_frame_class_valid_tuple excludes 'Undefined' for every vehicle type.

        GIVEN: All vehicle types in FRAME_CLASS_DICT
        WHEN: Calling get_frame_class_valid_tuple for each type
        THEN: The returned tuple must not contain 'Undefined' (invalid user selection)
        """
        for vtype in FRAME_CLASS_DICT:
            result = get_frame_class_valid_tuple(vtype)
            assert "Undefined" not in result, (
                f"'Undefined' must not appear in valid tuple for '{vtype}' (not a valid user selection)"
            )

    def test_get_frame_class_valid_tuple_returns_tuple_of_strings(self) -> None:
        """
        get_frame_class_valid_tuple returns a tuple of non-empty strings.

        GIVEN: A known vehicle type (ArduCopter)
        WHEN: Calling get_frame_class_valid_tuple
        THEN: A non-empty tuple of strings is returned, containing expected frame class names
        """
        result = get_frame_class_valid_tuple("ArduCopter")
        assert isinstance(result, tuple)
        assert len(result) > 0
        assert all(isinstance(name, str) for name in result)
        assert "Quad" in result
        assert "Hexa" in result

    def test_get_frame_class_valid_tuple_falls_back_to_arducopter_for_unknown_type(self) -> None:
        """
        get_frame_class_valid_tuple falls back to ArduCopter choices for unknown vehicle types.

        GIVEN: An unrecognised vehicle type string
        WHEN: Calling get_frame_class_valid_tuple
        THEN: The same result as for 'ArduCopter' is returned
        """
        unknown = get_frame_class_valid_tuple("UnknownVehicle")
        arducopter = get_frame_class_valid_tuple("ArduCopter")
        assert unknown == arducopter

    def test_get_frame_class_valid_tuple_heli_contains_heli_classes(self) -> None:
        """
        get_frame_class_valid_tuple for Heli contains Heli-specific choices.

        GIVEN: 'Heli' vehicle type
        WHEN: Calling get_frame_class_valid_tuple
        THEN: Result contains Heli, Heli_Dual, HeliQuad but not Quad or Hexa
        """
        result = get_frame_class_valid_tuple("Heli")
        assert "Heli" in result
        assert "Heli_Dual" in result
        assert "HeliQuad" in result
        assert "Quad" not in result
        assert "Hexa" not in result


class TestArduPlaneEscConnectionDict:
    """Tests for the ArduPlane entry in ESC_CONNECTION_DICT."""

    def test_arduplane_esc_connection_dict_exists(self) -> None:
        """
        ArduPlane has an entry in ESC_CONNECTION_DICT.

        GIVEN: The ESC_CONNECTION_DICT constant
        WHEN: Checking for the ArduPlane key
        THEN: The key must exist and its value must be a non-empty dict
        """
        assert "ArduPlane" in ESC_CONNECTION_DICT
        assert len(ESC_CONNECTION_DICT["ArduPlane"]) > 0

    def test_arduplane_esc_connection_dict_contains_dshot_protocols(self) -> None:
        """
        ArduPlane ESC dict includes DShot protocol entries.

        GIVEN: The ArduPlane sub-dict in ESC_CONNECTION_DICT
        WHEN: Collecting protocol names
        THEN: DShot600 and DShot300 must be present (VTOL motors support DShot)
        """
        protocols = {entry["protocol"] for entry in ESC_CONNECTION_DICT["ArduPlane"].values()}
        assert "DShot600" in protocols
        assert "DShot300" in protocols
        assert "Normal" in protocols

    def test_arduplane_esc_connection_dict_excludes_serial_esc_protocols(self) -> None:
        """
        ArduPlane ESC dict does not contain serial-only ESC protocols.

        GIVEN: The ArduPlane sub-dict in ESC_CONNECTION_DICT
        WHEN: Collecting protocol names
        THEN: FETtecOneWire, Torqeedo, and CoDevESC must NOT be present
        (ArduPlane VTOL uses Q_M_PWM_TYPE which does not support these)
        """
        protocols = {entry["protocol"] for entry in ESC_CONNECTION_DICT["ArduPlane"].values()}
        assert "FETtecOneWire" not in protocols
        assert "Torqeedo" not in protocols
        assert "CoDevESC" not in protocols
        # But DroneCAN (CAN protocol) must be present
        assert "DroneCAN" in protocols

    def test_arduplane_esc_connection_dict_entry_shape_matches_other_vehicles(self) -> None:
        """
        Each entry in the ArduPlane ESC dict has the same keys as other vehicle entries.

        GIVEN: The ArduPlane sub-dict and the ArduCopter sub-dict in ESC_CONNECTION_DICT
        WHEN: Comparing the key sets of individual entries
        THEN: Every ArduPlane entry must have the same set of keys as ArduCopter entries
        """
        arducopter_keys = {frozenset(entry.keys()) for entry in ESC_CONNECTION_DICT["ArduCopter"].values()}
        for code, entry in ESC_CONNECTION_DICT["ArduPlane"].items():
            assert frozenset(entry.keys()) in arducopter_keys, (
                f"ArduPlane ESC entry '{code}' has unexpected keys: {set(entry.keys())}"
            )
