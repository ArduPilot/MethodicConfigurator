#!/usr/bin/env python3

"""
Vehicle Components data model import tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

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

from ardupilot_methodic_configurator.data_model_vehicle_components_import import ComponentDataModelImport, is_single_bit_set

# pylint: disable=protected-access,too-many-public-methods,too-many-lines


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

    def test_system_validates_known_fc_manufacturers(self, basic_model) -> None:
        """
        System correctly validates flight controller manufacturer names.

        GIVEN: Known manufacturer names (Pixhawk, Matek, Holybro)
        WHEN: Validating manufacturer names
        THEN: Known manufacturers should be valid
        AND: Unknown manufacturers should be invalid
        """
        # Assert: Valid manufacturers return True
        assert basic_model.is_fc_manufacturer_valid("Pixhawk")
        assert basic_model.is_fc_manufacturer_valid("Matek")
        assert basic_model.is_fc_manufacturer_valid("Holybro")

        # Assert: Invalid manufacturers return False
        assert not basic_model.is_fc_manufacturer_valid("Unknown")
        assert not basic_model.is_fc_manufacturer_valid("ArduPilot")
        assert not basic_model.is_fc_manufacturer_valid("")
        assert not basic_model.is_fc_manufacturer_valid(None)

    def test_system_validates_known_fc_models(self, basic_model) -> None:
        """
        System correctly validates flight controller model names.

        GIVEN: Known model names (Pixhawk 6C, H743 SLIM, etc.)
        WHEN: Validating model names
        THEN: Known models should be valid
        AND: Unknown models should be invalid
        """
        # Assert: Valid models return True
        assert basic_model.is_fc_model_valid("Pixhawk 6C")
        assert basic_model.is_fc_model_valid("H743 SLIM")
        assert basic_model.is_fc_model_valid("Custom FC")

        # Assert: Invalid models return False
        assert not basic_model.is_fc_model_valid("Unknown")
        assert not basic_model.is_fc_model_valid("MAVLink")
        assert not basic_model.is_fc_model_valid("")
        assert not basic_model.is_fc_model_valid(None)

    def test_user_can_import_gnss_serial_connection_from_fc(self, realistic_model) -> None:
        """
        User can import GNSS receiver configuration with serial connection.

        GIVEN: Flight controller configured with GNSS on serial connection (GPS_TYPE=2, uBlox)
        WHEN: User imports FC parameters
        THEN: GNSS protocol should be set to uBlox
        AND: Connection type should be detected from serial port configuration
        """
        fc_parameters = {"GPS_TYPE": 2, "SERIAL3_PROTOCOL": 5}
        doc = {
            "GPS_TYPE": {"values": {"2": "uBlox"}},
            "SERIAL3_PROTOCOL": {"values": {"5": "GPS"}},
        }

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True):
            realistic_model.process_fc_parameters(fc_parameters, doc)

        protocol = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Protocol"))
        gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        assert protocol == "uBlox"
        assert gnss_type == "SERIAL3"

    def test_user_can_import_disabled_gnss_receiver(self, realistic_model) -> None:
        """
        User can import disabled GNSS receiver configuration.

        GIVEN: Flight controller with GPS_TYPE=0 (no GNSS)
        WHEN: User imports FC parameters
        THEN: GNSS type should be None
        AND: GNSS protocol should be None
        """
        fc_parameters = {"GPS_TYPE": 0}
        doc = {"GPS_TYPE": {"values": {"0": "None"}}}

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True):
            realistic_model.process_fc_parameters(fc_parameters, doc)

        gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        gnss_protocol = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Protocol"))
        assert gnss_type == "None"
        assert gnss_protocol == "None"

    def test_user_can_import_gnss_can1_connection(self, realistic_model) -> None:
        """
        User can import GNSS receiver on CAN1 bus with DroneCAN.

        GIVEN: Flight controller with GNSS on CAN1 (GPS_TYPE=9, DroneCAN)
        WHEN: User imports FC parameters
        THEN: GNSS connection type should be CAN1
        AND: GNSS protocol should be DroneCAN
        """
        fc_parameters = {"GPS_TYPE": 9, "CAN_D1_PROTOCOL": 1, "CAN_P1_DRIVER": 1}
        doc = {"GPS_TYPE": {"values": {"9": "DroneCAN"}}}

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True):
            realistic_model.process_fc_parameters(fc_parameters, doc)

        gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        gnss_protocol = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Protocol"))
        assert gnss_type == "CAN1"
        assert gnss_protocol == "DroneCAN"

    def test_user_can_import_gnss_can2_connection(self, realistic_model) -> None:
        """
        User can import GNSS receiver on CAN2 bus with DroneCAN.

        GIVEN: Flight controller with GNSS on CAN2 (GPS_TYPE=9, DroneCAN on second port)
        WHEN: User imports FC parameters
        THEN: GNSS connection type should be CAN2
        AND: GNSS protocol should be DroneCAN
        """
        fc_parameters = {"GPS_TYPE": 9, "CAN_D2_PROTOCOL": 1, "CAN_P2_DRIVER": 2}
        doc = {"GPS_TYPE": {"values": {"9": "DroneCAN"}}}

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True):
            realistic_model.process_fc_parameters(fc_parameters, doc)

        gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        gnss_protocol = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Protocol"))
        assert gnss_type == "CAN2"
        assert gnss_protocol == "DroneCAN"

    def test_user_can_import_single_rc_protocol_configuration(self, realistic_model) -> None:
        """
        User can import RC receiver with single protocol (power of 2).

        GIVEN: Flight controller with RC_PROTOCOLS=512 (CRSF, single protocol)
        WHEN: User imports FC parameters
        THEN: RC protocol should be set to CRSF
        AND: No warning should be logged
        """
        fc_parameters = {"RC_PROTOCOLS": 512}  # 2^9
        doc = {"RC_PROTOCOLS": {"values": {"512": "CRSF"}}}

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True):
            realistic_model.process_fc_parameters(fc_parameters, doc)

        rc_protocol = realistic_model.get_component_value(("RC Receiver", "FC Connection", "Protocol"))
        assert rc_protocol == "CRSF"

    def test_system_handles_multiple_rc_protocols_configuration(self, realistic_model) -> None:
        """
        User can import telemetry on serial port.

        GIVEN: Flight controller with telemetry on SERIAL1 (MAVLink2)
        WHEN: User imports FC parameters
        THEN: Telemetry type should be SERIAL1
        AND: Telemetry protocol should be MAVLink2
        """
        fc_parameters = {"SERIAL1_PROTOCOL": 2}
        doc = {"SERIAL1_PROTOCOL": {"values": {"2": "MAVLink2"}}}

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True):
            realistic_model.process_fc_parameters(fc_parameters, doc)

        telem_type = realistic_model.get_component_value(("Telemetry", "FC Connection", "Type"))
        telem_protocol = realistic_model.get_component_value(("Telemetry", "FC Connection", "Protocol"))
        assert telem_type == "SERIAL1"
        assert telem_protocol == "MAVLink2"

    @patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PORTS", ["SERIAL1", "SERIAL2"])
    @patch(
        "ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PROTOCOLS_DICT",
        {"30": {"component": "ESC", "protocol": "ESC Telem"}},
    )
    def test_system_detects_multiple_serial_esc_connections(self, realistic_model) -> None:
        """
        System detects when multiple serial ports have ESC telemetry.

        GIVEN: Flight controller with ESC telemetry on multiple serial ports
        WHEN: Importing serial port configuration
        THEN: First ESC connection should be used
        AND: Should return True indicating multiple ESC ports detected
        """
        fc_parameters = {"SERIAL1_PROTOCOL": 30, "SERIAL2_PROTOCOL": 30}

        result = realistic_model._set_serial_type_from_fc_parameters(fc_parameters)

        esc_type = realistic_model.get_component_value(("ESC", "FC Connection", "Type"))
        esc_protocol = realistic_model.get_component_value(("ESC", "FC Connection", "Protocol"))
        assert esc_type == "SERIAL1"
        assert esc_protocol == "ESC Telem"
        assert result is True  # Multiple ESCs

    @patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.SERIAL_PORTS", ["SERIAL1"])
    def test_system_handles_invalid_serial_protocol_value(self, realistic_model) -> None:
        """
        System handles invalid SERIAL_PROTOCOL values gracefully.

        GIVEN: Flight controller with invalid serial protocol value
        WHEN: Importing serial port configuration
        THEN: Error should be logged
        AND: Should return False (no processing)
        """
        fc_parameters = {"SERIAL1_PROTOCOL": "invalid"}

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            result = realistic_model._set_serial_type_from_fc_parameters(fc_parameters)

        assert result is False

    @patch(
        "ardupilot_methodic_configurator.data_model_vehicle_components_import.MOT_PWM_TYPE_DICT",
        {"6": {"protocol": "DShot600"}},
    )
    def test_system_imports_esc_on_main_outputs(self, realistic_model) -> None:
        """
        System correctly imports ESC connected to main PWM outputs.

        GIVEN: Flight controller with DShot600 ESC on main outputs (motors on SERVO outputs)
        WHEN: Importing ESC parameters
        THEN: ESC type should be Main Out
        AND: ESC protocol should be DShot600
        """
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
    def test_system_imports_esc_aio_configuration(self, realistic_model) -> None:
        """
        System correctly imports ESC in AIO (All-In-One) configuration.

        GIVEN: Flight controller with DShot600 but no motors on SERVO outputs
        WHEN: Importing ESC parameters
        THEN: ESC type should be AIO
        AND: ESC protocol should be DShot600
        """
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

    def test_user_can_import_battery_monitor_configuration(self, realistic_model) -> None:
        """
        User can import battery monitor configuration.

        GIVEN: Flight controller with analog battery monitor (BATT_MONITOR=4)
        WHEN: User imports FC parameters
        THEN: Battery type should be Analog
        AND: Battery protocol should be Analog Voltage and Current
        """
        fc_parameters = {"BATT_MONITOR": 4}
        doc = {"BATT_MONITOR": {"values": {"4": "Analog Voltage and Current"}}}

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True):
            realistic_model.process_fc_parameters(fc_parameters, doc)

        batt_type = realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Type"))
        batt_protocol = realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Protocol"))
        assert batt_type == "Analog"
        assert batt_protocol == "Analog Voltage and Current"

    def test_user_can_import_motor_poles_for_dshot(self, realistic_model) -> None:
        """
        User can import motor pole count for DShot ESCs.

        GIVEN: Flight controller with DShot ESC and motor poles configured
        WHEN: User imports FC parameters
        THEN: Motor poles should be set from SERVO_BLH_POLES parameter
        """
        fc_parameters = {"MOT_PWM_TYPE": 6, "SERVO_BLH_POLES": 14}
        doc = {"MOT_PWM_TYPE": {"values": {"6": "DShot600"}}}

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True):
            realistic_model.process_fc_parameters(fc_parameters, doc)

        motor_poles = realistic_model.get_component_value(("Motors", "Specifications", "Poles"))
        assert motor_poles == 14

    def test_user_can_import_motor_poles_for_fettec(self, realistic_model) -> None:
        """
        User can import motor pole count for FETtec ESCs.

        GIVEN: Flight controller with FETtec ESC and motor poles configured
        WHEN: User imports FC parameters
        THEN: Motor poles should be set from SERVO_FTW_POLES parameter
        """
        fc_parameters = {"MOT_PWM_TYPE": 0, "SERVO_FTW_MASK": 15, "SERVO_FTW_POLES": 12}
        doc: dict[str, Any] = {}

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True):
            realistic_model.process_fc_parameters(fc_parameters, doc)

        motor_poles = realistic_model.get_component_value(("Motors", "Specifications", "Poles"))
        assert motor_poles == 12

    def test_system_imports_complete_fc_configuration(self, realistic_model) -> None:
        """
        System successfully imports complete flight controller configuration.

        GIVEN: Flight controller with all components configured (GNSS, serial, ESC, battery)
        WHEN: Processing all FC parameters together
        THEN: All components should be configured correctly
        AND: No errors should occur
        """
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

    def test_system_handles_empty_fc_configuration(self, realistic_model) -> None:
        """
        System handles empty flight controller configuration gracefully.

        GIVEN: Empty FC parameters and documentation
        WHEN: Processing FC parameters
        THEN: System should not crash
        AND: No components should be configured
        """
        fc_parameters: dict[str, float] = {}
        doc: dict[str, Any] = {}

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True):
            realistic_model.process_fc_parameters(fc_parameters, doc)

    def test_system_skips_disabled_serial_ports(self, realistic_model) -> None:
        """
        System defaults ESC to AIO when no servo functions defined.

        GIVEN: Flight controller with MOT_PWM_TYPE but no SERVO_FUNCTION parameters
        WHEN: Importing ESC configuration
        THEN: ESC type should default to AIO
        """
        fc_parameters = {"MOT_PWM_TYPE": 6}  # No SERVO functions defined
        doc = {"MOT_PWM_TYPE": {"values": {"6": "DShot600"}}}

        realistic_model._set_esc_type_from_fc_parameters(fc_parameters, doc)

        esc_type = realistic_model.get_component_value(("ESC", "FC Connection", "Type"))
        assert esc_type == "AIO"  # Should default to AIO when no main out functions

    def test_system_falls_back_to_mot_pwm_dict_when_doc_empty(self, realistic_model) -> None:
        """
        System falls back to MOT_PWM_TYPE_DICT when documentation is empty.

        GIVEN: Empty documentation but MOT_PWM_TYPE_DICT available
        WHEN: Importing ESC configuration
        THEN: MOT_PWM_TYPE_DICT should be used as fallback
        AND: ESC protocol should be correctly identified
        """
        with patch(
            "ardupilot_methodic_configurator.data_model_vehicle_components_import.MOT_PWM_TYPE_DICT",
            {"6": {"protocol": "DShot600"}},
        ):
            fc_parameters = {"MOT_PWM_TYPE": 6}
            doc: dict[str, Any] = {}  # Empty doc should trigger fallback

            realistic_model._set_esc_type_from_fc_parameters(fc_parameters, doc)

            esc_protocol = realistic_model.get_component_value(("ESC", "FC Connection", "Protocol"))
            assert esc_protocol == "DShot600"

    def test_system_handles_esc_protocol_not_found(self, realistic_model) -> None:
        """
        System handles ESC protocol not found in either documentation or dictionary.

        GIVEN: MOT_PWM_TYPE not in documentation or MOT_PWM_TYPE_DICT
        WHEN: Importing ESC configuration
        THEN: System should handle gracefully without setting protocol
        """
        fc_parameters = {"MOT_PWM_TYPE": 999}  # Non-existent type
        doc = {"MOT_PWM_TYPE": {"values": {"6": "DShot600"}}}  # Doesn't contain 999

        realistic_model._set_esc_type_from_fc_parameters(fc_parameters, doc)
        # Should handle gracefully without setting protocol

    def test_system_handles_battery_monitor_key_error(self, realistic_model) -> None:
        """
        System handles KeyError for unknown BATT_MONITOR values.

        GIVEN: BATT_MONITOR value not in BATT_MONITOR_CONNECTION dict
        WHEN: Importing battery configuration
        THEN: Error should be logged
        AND: System should not crash
        """  # pylint: disable=duplicate-code  # Common error handling test pattern
        fc_parameters = {"BATT_MONITOR": 999}  # Non-existent key

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)
        # pylint: enable=duplicate-code

    def test_system_handles_battery_monitor_type_error(self, realistic_model) -> None:
        """
        System handles TypeError when converting BATT_MONITOR to integer.

        GIVEN: BATT_MONITOR with None or non-convertible value
        WHEN: Importing battery configuration
        THEN: Error should be logged
        AND: System should not crash
        """  # pylint: disable=duplicate-code  # Common error handling test pattern
        fc_parameters = {"BATT_MONITOR": None}  # Will cause TypeError in int()

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)
        # pylint: enable=duplicate-code

    def test_user_can_import_battery_capacity_from_fc_parameters(self, realistic_model) -> None:
        """
        User can import battery capacity from flight controller parameters.

        GIVEN: Flight controller parameters with BATT_CAPACITY set
        WHEN: Importing battery configuration
        THEN: Battery capacity should be set in data model
        """
        fc_parameters = {"BATT_CAPACITY": 5000}

        realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

        capacity = realistic_model.get_component_value(("Battery", "Specifications", "Capacity mAh"))
        assert capacity == 5000

    def test_system_handles_zero_battery_capacity(self, realistic_model) -> None:
        """
        System ignores zero battery capacity from FC parameters.

        GIVEN: Flight controller with BATT_CAPACITY set to 0
        WHEN: Importing battery configuration
        THEN: Battery capacity should not be updated
        """
        # Set initial capacity to something non-zero
        realistic_model.set_component_value(("Battery", "Specifications", "Capacity mAh"), 1000)

        fc_parameters = {"BATT_CAPACITY": 0}
        realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

        capacity = realistic_model.get_component_value(("Battery", "Specifications", "Capacity mAh"))
        # Should remain at initial value since 0 is ignored
        assert capacity == 1000

    def test_system_handles_invalid_battery_capacity_type(self, realistic_model) -> None:
        """
        System handles invalid BATT_CAPACITY value gracefully.

        GIVEN: FC parameters with non-integer BATT_CAPACITY value
        WHEN: Importing battery configuration
        THEN: Error should be logged
        AND: System should not crash
        """
        fc_parameters = {"BATT_CAPACITY": "invalid"}

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

    def test_system_handles_none_battery_capacity(self, realistic_model) -> None:
        """
        System handles None BATT_CAPACITY value gracefully.

        GIVEN: FC parameters with BATT_CAPACITY set to None
        WHEN: Importing battery configuration
        THEN: Error should be logged
        AND: System should not crash
        """
        fc_parameters = {"BATT_CAPACITY": None}

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

    def test_system_handles_negative_battery_capacity(self, realistic_model) -> None:
        """
        System ignores negative battery capacity from FC parameters.

        GIVEN: Flight controller with BATT_CAPACITY set to negative value
        WHEN: Importing battery configuration
        THEN: Battery capacity should not be updated
        """
        # Set initial capacity to something non-zero
        realistic_model.set_component_value(("Battery", "Specifications", "Capacity mAh"), 1000)

        fc_parameters = {"BATT_CAPACITY": -100}
        realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

        capacity = realistic_model.get_component_value(("Battery", "Specifications", "Capacity mAh"))
        # Should remain at initial value since negative is ignored
        assert capacity == 1000

    def test_system_imports_both_battery_monitor_and_capacity(self, realistic_model) -> None:
        """
        System imports both battery monitor type and capacity together.

        GIVEN: FC parameters with both BATT_MONITOR and BATT_CAPACITY
        WHEN: Importing battery configuration
        THEN: Both monitor type and capacity should be set
        """
        fc_parameters = {"BATT_MONITOR": 4, "BATT_CAPACITY": 6500}

        realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

        batt_type = realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Type"))
        capacity = realistic_model.get_component_value(("Battery", "Specifications", "Capacity mAh"))

        assert batt_type == "Analog"
        assert capacity == 6500

    def test_user_can_estimate_cell_count_from_mot_bat_volt_max(self, realistic_model) -> None:
        """
        User can estimate battery cell count from MOT_BAT_VOLT_MAX parameter.

        GIVEN: Flight controller with MOT_BAT_VOLT_MAX configured for 4S Lipo (16.8V)
        WHEN: Importing battery configuration
        THEN: Cell count should be estimated as 4 (16.8V / 4.2V per cell)
        """
        # Set Lipo chemistry (4.2V per cell max)
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")

        fc_parameters = {"MOT_BAT_VOLT_MAX": 16.8}  # 4S Lipo: 4 * 4.2V = 16.8V

        realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

        cell_count = realistic_model.get_component_value(("Battery", "Specifications", "Number of cells"))
        assert cell_count == 4

    def test_user_can_estimate_cell_count_from_batt_low_volt(self, realistic_model) -> None:
        """
        User can estimate battery cell count from BATT_LOW_VOLT parameter.

        GIVEN: Flight controller with BATT_LOW_VOLT configured for 6S Lipo (21.6V)
        WHEN: Importing battery configuration without MOT_BAT_VOLT_MAX
        THEN: Cell count should be estimated as 6 (21.6V / 3.6V per cell)
        """
        # Set Lipo chemistry (3.6V per cell low)
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")

        fc_parameters = {"BATT_LOW_VOLT": 21.6}  # 6S Lipo: 6 * 3.6V = 21.6V

        realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

        cell_count = realistic_model.get_component_value(("Battery", "Specifications", "Number of cells"))
        assert cell_count == 6

    def test_user_can_estimate_cell_count_from_batt_crt_volt(self, realistic_model) -> None:
        """
        User can estimate battery cell count from BATT_CRT_VOLT parameter.

        GIVEN: Flight controller with BATT_CRT_VOLT configured for 3S Lipo (9.9V)
        WHEN: Importing battery configuration without MOT_BAT_VOLT_MAX or BATT_LOW_VOLT
        THEN: Cell count should be estimated as 3 (9.9V / 3.3V per cell)
        """
        # Set Lipo chemistry (3.3V per cell critical)
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")

        fc_parameters = {"BATT_CRT_VOLT": 9.9}  # 3S Lipo: 3 * 3.3V = 9.9V

        realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

        cell_count = realistic_model.get_component_value(("Battery", "Specifications", "Number of cells"))
        assert cell_count == 3

    def test_system_prioritizes_mot_bat_volt_max_for_cell_estimation(self, realistic_model) -> None:
        """
        System prioritizes MOT_BAT_VOLT_MAX over other voltage parameters for cell estimation.

        GIVEN: FC with multiple voltage parameters that would give different cell counts
        WHEN: Importing battery configuration
        THEN: Cell count should be estimated from MOT_BAT_VOLT_MAX (highest priority)
        """
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")

        fc_parameters = {
            "MOT_BAT_VOLT_MAX": 16.8,  # 4S
            "BATT_LOW_VOLT": 18.0,  # Would estimate 5S
            "BATT_CRT_VOLT": 19.8,  # Would estimate 6S
        }

        realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

        cell_count = realistic_model.get_component_value(("Battery", "Specifications", "Number of cells"))
        assert cell_count == 4  # From MOT_BAT_VOLT_MAX

    def test_system_handles_liion_cell_count_estimation(self, realistic_model) -> None:
        """
        System correctly estimates cell count for LiIon batteries with different voltages.

        GIVEN: Flight controller configured for 14S LiIon battery
        WHEN: Importing battery configuration
        THEN: Cell count should be estimated as 14 (57.4V / 4.1V per cell)
        """
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "LiIon")

        fc_parameters = {"MOT_BAT_VOLT_MAX": 57.4}  # 14S LiIon: 14 * 4.1V = 57.4V

        realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

        cell_count = realistic_model.get_component_value(("Battery", "Specifications", "Number of cells"))
        assert cell_count == 14

    def test_system_handles_zero_voltage_for_cell_estimation(self, realistic_model) -> None:
        """
        System ignores zero voltage values when estimating cell count.

        GIVEN: Flight controller with voltage parameters set to 0
        WHEN: Importing battery configuration
        THEN: Cell count should not be set
        """
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")
        initial_cells = realistic_model.get_component_value(("Battery", "Specifications", "Number of cells"))

        fc_parameters = {
            "MOT_BAT_VOLT_MAX": 0,
            "BATT_LOW_VOLT": 0,
            "BATT_CRT_VOLT": 0,
        }

        realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

        cell_count = realistic_model.get_component_value(("Battery", "Specifications", "Number of cells"))
        assert cell_count == initial_cells  # Should not change

    def test_system_handles_invalid_voltage_type_for_cell_estimation(self, realistic_model) -> None:
        """
        System handles invalid voltage parameter types gracefully.

        GIVEN: FC with non-numeric voltage values
        WHEN: Importing battery configuration
        THEN: Error should be logged and system should not crash
        """
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")

        fc_parameters = {"MOT_BAT_VOLT_MAX": "invalid"}

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

    def test_system_handles_out_of_range_cell_count(self, realistic_model) -> None:
        """
        System ignores unrealistic cell count estimations.

        GIVEN: Flight controller with voltage that would estimate >50 cells
        WHEN: Importing battery configuration
        THEN: Cell count should not be set (out of valid range)
        """
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")
        initial_cells = realistic_model.get_component_value(("Battery", "Specifications", "Number of cells"))

        fc_parameters = {"MOT_BAT_VOLT_MAX": 300.0}  # Would estimate ~71 cells

        realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

        cell_count = realistic_model.get_component_value(("Battery", "Specifications", "Number of cells"))
        assert cell_count == initial_cells  # Should not change

    def test_system_estimates_cells_with_default_chemistry(self, realistic_model) -> None:
        """
        System uses default Lipo chemistry if battery chemistry not set.

        GIVEN: Flight controller without battery chemistry configured
        WHEN: Importing battery configuration with voltage parameters
        THEN: Cell count should be estimated using Lipo voltages as default
        """
        # Ensure chemistry is not a valid one (empty or invalid)
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "")

        fc_parameters = {"MOT_BAT_VOLT_MAX": 25.2}  # 6S Lipo: 6 * 4.2V = 25.2V

        realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

        cell_count = realistic_model.get_component_value(("Battery", "Specifications", "Number of cells"))
        assert cell_count == 6  # Should estimate as Lipo

    def test_system_preserves_motor_poles_when_no_dshot_or_fettec(self, realistic_model) -> None:
        """
        System preserves existing motor poles when neither DShot nor FETtec configured.

        GIVEN: Flight controller without DShot or FETtec ESC
        WHEN: Importing motor specifications
        THEN: Motor poles should not be modified
        """
        initial_poles = realistic_model.get_component_value(("Motors", "Specifications", "Poles"))

        fc_parameters = {
            "MOT_PWM_TYPE": 0,  # Normal PWM, not DShot
            "SERVO_FTW_MASK": 0,  # No FETtec
        }

        realistic_model._set_motor_poles_from_fc_parameters(fc_parameters)

        # Should not change motor poles
        final_poles = realistic_model.get_component_value(("Motors", "Specifications", "Poles"))
        assert final_poles == initial_poles

    def test_system_handles_dshot_without_poles_parameter(self, realistic_model) -> None:
        """
        System handles DShot ESC configuration without pole count parameter.

        GIVEN: Flight controller with DShot but missing SERVO_BLH_POLES
        WHEN: Importing motor specifications
        THEN: System should handle gracefully without setting poles
        """
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

    def test_system_handles_fettec_without_mask_parameter(self, realistic_model) -> None:
        """
        System handles FETtec configuration without mask parameter.

        GIVEN: Flight controller with FETtec poles but missing SERVO_FTW_MASK
        WHEN: Importing motor specifications
        THEN: Motor poles should not be set
        """
        fc_parameters = {
            "MOT_PWM_TYPE": 0,  # Not DShot
            "SERVO_FTW_POLES": 12,
            # Missing SERVO_FTW_MASK
        }

        realistic_model._set_motor_poles_from_fc_parameters(fc_parameters)
        # Should not set poles without mask

    def test_system_handles_fettec_with_zero_mask(self, realistic_model) -> None:
        """
        System handles FETtec configuration with zero mask value.

        GIVEN: Flight controller with SERVO_FTW_MASK=0 (no FETtec ESCs)
        WHEN: Importing motor specifications
        THEN: Motor poles should not be set
        """
        fc_parameters = {
            "MOT_PWM_TYPE": 0,  # Not DShot
            "SERVO_FTW_MASK": 0,  # Zero mask
            "SERVO_FTW_POLES": 12,
        }

        realistic_model._set_motor_poles_from_fc_parameters(fc_parameters)
        # Should not set poles with zero mask

    def test_user_can_import_complete_vehicle_configuration(self, realistic_model, sample_doc_dict) -> None:
        """
        User can successfully import complete vehicle configuration from flight controller.

        GIVEN: Flight controller with all components configured (GNSS, RC, telemetry, ESC, battery, motors)
        WHEN: Processing all FC parameters in single operation
        THEN: All components should be correctly imported
        AND: GNSS should be on SERIAL2
        AND: RC receiver should be on SERIAL3 with CRSF protocol
        AND: ESC should be Main Out with DShot600
        AND: Motor poles should be 14
        AND: Battery should be analog voltage and current
        """
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

    def test_system_prioritizes_serial_esc_over_pwm_esc(self, realistic_model, sample_doc_dict) -> None:
        """
        System correctly prioritizes serial ESC configuration over PWM ESC.

        GIVEN: Flight controller with both serial ESC and PWM ESC configured
        WHEN: Processing ESC parameters
        THEN: Serial ESC configuration should take precedence
        AND: PWM ESC configuration should be ignored
        """
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

    def test_system_assigns_different_components_to_different_serial_ports(self, realistic_model, sample_doc_dict) -> None:
        """
        System correctly assigns different component types to different serial ports.

        GIVEN: Flight controller with GNSS, RC, and telemetry on different serial ports
        WHEN: Processing serial port configuration
        THEN: Each component should be assigned to correct serial port
        AND: No port conflicts should occur
        """
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

    def test_system_handles_invalid_documentation_with_fallback(self, realistic_model) -> None:
        """
        System uses fallback dictionaries when documentation is invalid or incomplete.

        GIVEN: Empty or invalid documentation
        WHEN: Processing FC parameters
        THEN: System should use fallback dictionaries
        AND: Parameters should still be processed correctly
        """
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

    def test_system_attempts_verification_for_all_dictionaries(self, realistic_model) -> None:
        """
        System attempts to verify all protocol dictionaries even when verification fails.

        GIVEN: Flight controller parameters and documentation that fails verification
        WHEN: Processing FC parameters
        THEN: Verification should be attempted for all 5 dictionaries
        AND: Processing should continue despite verification failures
        """
        fc_parameters = {
            "GPS_TYPE": 2,
            "SERIAL1_PROTOCOL": 5,
            "RC_PROTOCOLS": 512,
            "MOT_PWM_TYPE": 6,
            "BATT_MONITOR": 4,
        }

        doc = {"GPS_TYPE": {"values": {}}}  # Include GPS_TYPE so verification is called

        # Mock all verifications to fail
        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=False) as mock_verify:
            realistic_model.process_fc_parameters(fc_parameters, doc)

            # Should call verification 5 times (once for each dictionary)
            assert mock_verify.call_count == 5

    def test_system_correctly_validates_rc_protocol_power_of_two(self, realistic_model) -> None:
        """
        System correctly validates RC_PROTOCOLS as power-of-2 bitmask values.

        GIVEN: Various RC_PROTOCOLS values (powers of 2 and non-powers)
        WHEN: Validating each value
        THEN: Valid powers of 2 should be accepted
        AND: Invalid values (0, non-powers) should be rejected
        """
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

    def test_system_correctly_detects_gnss_can_port_assignment(self, realistic_model) -> None:
        """
        System correctly detects which CAN port is used for GNSS receiver.

        GIVEN: Flight controller with GNSS on either CAN1 or CAN2
        WHEN: Importing GNSS configuration
        THEN: Correct CAN port should be identified
        AND: DroneCAN protocol should be recognized
        """
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

    def test_system_detects_main_out_vs_aio_from_servo_functions(self, realistic_model) -> None:
        """
        System correctly distinguishes Main Out vs AIO ESC based on servo functions.

        GIVEN: Various combinations of servo function assignments
        WHEN: Importing ESC configuration
        THEN: Main Out should be detected when motor functions present on SERVO outputs
        AND: AIO should be detected when no motor functions on SERVO outputs
        """
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

    def test_gps1_type_parameter_support(self, realistic_model) -> None:
        """
        System correctly processes GPS1_TYPE parameter for ArduPilot 4.6+ firmware.

        GIVEN: Flight controller parameters with GPS1_TYPE set to uBlox (type 2)
        WHEN: GNSS type is imported from FC parameters
        THEN: The GNSS protocol should be set to uBlox
        AND: GPS1_TYPE should function identically to legacy GPS_TYPE
        """
        # Arrange: Configure FC with GPS1_TYPE parameter (ArduPilot 4.6+)
        fc_parameters = {"GPS1_TYPE": 2}

        # Act: Import GNSS configuration from flight controller
        realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)

        # Assert: Protocol correctly identified from GPS1_TYPE
        protocol = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Protocol"))
        assert protocol == "uBlox", "GPS1_TYPE should work just like GPS_TYPE"

    def test_gps1_type_takes_precedence_over_gps_type(self, realistic_model) -> None:
        """
        GPS1_TYPE parameter takes precedence over legacy GPS_TYPE when both exist.

        GIVEN: Flight controller has both GPS_TYPE (legacy) and GPS1_TYPE (new) parameters
        WHEN: GNSS configuration is imported
        THEN: GPS1_TYPE value should be used
        AND: GPS_TYPE value should be ignored
        """
        # Arrange: FC with both legacy and new GPS parameters
        fc_parameters = {
            "GPS_TYPE": 5,  # NMEA (legacy, should be ignored)
            "GPS1_TYPE": 2,  # uBlox (new, should be used)
        }

        # Act: Import GNSS configuration
        realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)

        # Assert: GPS1_TYPE takes precedence
        protocol = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Protocol"))
        assert protocol == "uBlox", "GPS1_TYPE should take precedence over GPS_TYPE"

    def test_gps_type_fallback_when_gps1_type_missing(self, realistic_model) -> None:
        """
        System maintains backward compatibility with legacy GPS_TYPE parameter.

        GIVEN: Flight controller with older firmware using GPS_TYPE (not GPS1_TYPE)
        WHEN: GNSS configuration is imported
        THEN: GPS_TYPE value should be used correctly
        AND: Backward compatibility with pre-4.6 firmware should be maintained
        """
        # Arrange: Older FC firmware with legacy GPS_TYPE only
        fc_parameters = {"GPS_TYPE": 5}  # NMEA

        # Act: Import GNSS configuration
        realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)

        # Assert: Legacy parameter works correctly
        protocol = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Protocol"))
        assert protocol == "NMEA", "GPS_TYPE should work when GPS1_TYPE is absent"

    def test_gps1_type_can_connection(self, realistic_model) -> None:
        """Test GPS1_TYPE with CAN connection (DroneCAN)."""
        fc_parameters = {
            "GPS1_TYPE": 9,  # DroneCAN
            "CAN_D1_PROTOCOL": 1,  # DroneCAN
            "CAN_P1_DRIVER": 1,  # First CAN driver
        }

        realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)
        gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        protocol = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Protocol"))

        assert gnss_type == "CAN1", "GPS1_TYPE should support CAN connections"
        assert protocol == "DroneCAN"

    def test_gps1_type_serial_connection(self, realistic_model) -> None:
        """Test GPS1_TYPE with serial connection detection."""
        fc_parameters = {
            "GPS1_TYPE": 2,  # uBlox (SERIAL)
            "SERIAL3_PROTOCOL": 5,  # GPS protocol on SERIAL3
        }

        realistic_model._set_gnss_type_from_fc_parameters(fc_parameters)
        realistic_model._set_serial_type_from_fc_parameters(fc_parameters)

        gnss_type = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        protocol = realistic_model.get_component_value(("GNSS Receiver", "FC Connection", "Protocol"))

        assert gnss_type == "SERIAL3", "GPS1_TYPE serial connection should be detected from SERIAL_PROTOCOL"
        assert protocol == "uBlox"

    def test_gps1_type_verification_in_process_fc_parameters(self, realistic_model) -> None:
        """Test that process_fc_parameters correctly verifies GPS1_TYPE documentation."""
        fc_parameters = {"GPS1_TYPE": 2}
        doc = {
            "GPS1_TYPE": {
                "values": {
                    "0": "None",
                    "1": "AUTO",
                    "2": "uBlox",
                }
            }
        }

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True) as mock_verify:
            realistic_model.process_fc_parameters(fc_parameters, doc)

            # Should call verification with GPS1_TYPE (not GPS_TYPE)
            calls = [call[0] for call in mock_verify.call_args_list]
            assert any("GPS1_TYPE" in str(call) for call in calls), "Should verify GPS1_TYPE when present in doc"

    def test_gps_type_verification_when_gps1_type_absent(self, realistic_model) -> None:
        """Test that process_fc_parameters falls back to GPS_TYPE verification for older firmware."""
        fc_parameters = {"GPS_TYPE": 2}
        doc = {
            "GPS_TYPE": {  # Older firmware uses GPS_TYPE
                "values": {
                    "0": "None",
                    "1": "AUTO",
                    "2": "uBlox",
                }
            }
        }

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True) as mock_verify:
            realistic_model.process_fc_parameters(fc_parameters, doc)

            # Should call verification with GPS_TYPE (not GPS1_TYPE)
            calls = [call[0] for call in mock_verify.call_args_list]
            assert any("GPS_TYPE" in str(call) for call in calls), "Should verify GPS_TYPE when GPS1_TYPE absent"

    def test_rc_protocols_multiple_bits_warning(self, realistic_model, caplog) -> None:
        """
        System warns user when RC_PROTOCOLS has ambiguous multiple protocol configuration.

        GIVEN: Flight controller configured with multiple RC protocols enabled simultaneously
        WHEN: RC protocol configuration is imported
        THEN: A warning should be logged about the ambiguous configuration
        AND: The system should not set a specific protocol (due to ambiguity)
        """
        # Arrange: FC with multiple RC protocols enabled (PPM + IBUS)
        fc_parameters = {
            "RC_PROTOCOLS": 3,  # 0b0011 - both PPM and IBUS enabled
        }

        # Act: Import serial configuration and capture warnings
        with caplog.at_level("WARNING"):
            realistic_model._set_serial_type_from_fc_parameters(fc_parameters)

            # Assert: Warning logged about multiple protocols
            assert len(caplog.records) >= 1, "Should warn about multiple protocols"
            log_message = caplog.text.lower()
            assert "multiple" in log_message or "protocol" in log_message, "Warning should mention multiple protocols"

    def test_rc_protocols_single_bit_no_warning(self, realistic_model) -> None:
        """
        System processes single RC protocol configuration without warnings.

        GIVEN: Flight controller configured with exactly one RC protocol (CRSF)
        WHEN: RC protocol configuration is imported
        THEN: No warning should be logged
        AND: The single protocol should be identified unambiguously
        """
        # Arrange: FC with single RC protocol enabled
        fc_parameters = {
            "RC_PROTOCOLS": 512,  # 2^9 - CRSF protocol only
        }

        # Act: Import serial configuration
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning") as mock_warn:
            realistic_model._set_serial_type_from_fc_parameters(fc_parameters)

            # Assert: No warning for valid single-protocol configuration
            mock_warn.assert_not_called()

    def test_rc_protocols_zero_no_warning(self, realistic_model) -> None:
        """
        System handles disabled RC protocols configuration without warnings.

        GIVEN: Flight controller with RC_PROTOCOLS set to zero (all protocols disabled)
        WHEN: RC protocol configuration is imported
        THEN: No warning should be logged
        AND: This represents a valid default/disabled state
        """
        # Arrange: FC with all RC protocols disabled
        fc_parameters = {
            "RC_PROTOCOLS": 0,  # No protocols enabled (valid default)
        }

        # Act: Import serial configuration
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning") as mock_warn:
            realistic_model._set_serial_type_from_fc_parameters(fc_parameters)

            # Assert: No warning for disabled state (common default)
            mock_warn.assert_not_called()

    def test_rc_protocols_various_multiple_bit_combinations(self, realistic_model, caplog) -> None:
        """
        System consistently warns for all invalid multi-protocol configurations.

        GIVEN: Flight controller with various multi-protocol bitmask combinations
        WHEN: RC protocol configuration is imported for each combination
        THEN: A warning should be logged for every multi-protocol configuration
        AND: The warning behavior should be consistent across all combinations
        """
        # Arrange: Multiple test cases with different bit combinations
        test_cases = [
            3,  # PPM + IBUS
            5,  # PPM + DSM
            7,  # PPM + IBUS + SBUS
            12,  # SBUS_NI + DSM
            255,  # Many protocols
            1023,  # All protocols
        ]

        for rc_protocols_value in test_cases:
            # Arrange: FC with multi-protocol configuration
            fc_parameters = {"RC_PROTOCOLS": rc_protocols_value}

            # Act: Import configuration and capture warnings
            caplog.clear()  # Clear logs between iterations
            with caplog.at_level("WARNING"):
                realistic_model._set_serial_type_from_fc_parameters(fc_parameters)

                # Assert: Warning logged for each multi-protocol case
                assert len(caplog.records) >= 1, f"Should warn for RC_PROTOCOLS={rc_protocols_value}"

    def test_is_single_bit_set_helper_function(self) -> None:
        """
        Bitmask helper correctly identifies single-bit values (powers of 2).

        GIVEN: Various integer values representing bitmasks
        WHEN: Testing if exactly one bit is set
        THEN: Powers of 2 should return True (single bit set)
        AND: Non-powers of 2 should return False (zero, multiple, or invalid)
        """
        # Assert: Powers of 2 (single bit set) return True
        assert is_single_bit_set(1) is True  # 0b0001
        assert is_single_bit_set(2) is True  # 0b0010
        assert is_single_bit_set(4) is True  # 0b0100
        assert is_single_bit_set(8) is True  # 0b1000
        assert is_single_bit_set(16) is True  # 0b10000
        assert is_single_bit_set(512) is True  # 0b1000000000
        assert is_single_bit_set(1024) is True  # 0b10000000000

        # Assert: Non-powers of 2 (multiple bits) return False
        assert is_single_bit_set(3) is False  # 0b0011 - two bits
        assert is_single_bit_set(5) is False  # 0b0101 - two bits
        assert is_single_bit_set(7) is False  # 0b0111 - three bits
        assert is_single_bit_set(255) is False  # 0b11111111 - eight bits

        # Assert: Edge cases return False
        assert is_single_bit_set(0) is False  # No bits set
        assert is_single_bit_set(-1) is False  # Negative number
        assert is_single_bit_set(-4) is False  # Negative power of 2

    def test_user_can_import_complete_battery_configuration(self, realistic_model) -> None:
        """
        User can import complete battery configuration including monitor, capacity, and cell count.

        GIVEN: Flight controller with BATT_MONITOR, BATT_CAPACITY, and MOT_BAT_VOLT_MAX configured
        WHEN: Processing FC parameters through complete import flow
        THEN: Battery monitor connection, capacity, and estimated cell count should be imported
        """
        # Set Lipo chemistry for cell count estimation
        realistic_model.set_component_value(("Battery", "Specifications", "Chemistry"), "Lipo")

        fc_parameters = {
            "BATT_MONITOR": 4,
            "BATT_CAPACITY": 6500,
            "MOT_BAT_VOLT_MAX": 25.2,  # 6S Lipo
        }
        doc: dict[str, Any] = {
            "SERIAL1_PROTOCOL": {"values": {}},
            "BATT_MONITOR": {"values": {"4": "Analog Voltage and Current"}},
            "GPS1_TYPE": {"values": {}},
            "MOT_PWM_TYPE": {"values": {}},
            "RC_PROTOCOLS": {"Bitmask": {}},
        }

        realistic_model.process_fc_parameters(fc_parameters, doc)

        # Verify battery monitor connection
        batt_type = realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Type"))
        batt_protocol = realistic_model.get_component_value(("Battery Monitor", "FC Connection", "Protocol"))

        # Verify battery capacity
        capacity = realistic_model.get_component_value(("Battery", "Specifications", "Capacity mAh"))

        # Verify cell count estimation
        cell_count = realistic_model.get_component_value(("Battery", "Specifications", "Number of cells"))

        assert batt_type == "Analog"
        assert batt_protocol == "Analog Voltage and Current"
        assert capacity == 6500
        assert cell_count == 6
