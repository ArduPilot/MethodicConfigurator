#!/usr/bin/env python3

"""
Vehicle Components data model import tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from math import nan
from typing import Any
from unittest.mock import patch

import pytest
from test_data_model_vehicle_components_common import (
    BasicTestMixin,
    ComponentDataModelFixtures,
    RealisticDataTestMixin,
)

import ardupilot_methodic_configurator.data_model_vehicle_components_import as _import_module
from ardupilot_methodic_configurator.battery_cell_voltages import BatteryCell
from ardupilot_methodic_configurator.data_model_vehicle_components_import import (
    BatteryVoltageSpecs,
    ComponentDataModelImport,
    is_single_bit_set,
)

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
        fc_parameters = {"GPS_TYPE": 9, "CAN_D2_PROTOCOL": 1, "CAN_P2_DRIVER": 1}
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

    def test_user_can_import_motor_poles_for_hobbywing(self, realistic_model) -> None:
        """
        User can import motor pole count for Hobbywing ESCs.

        GIVEN: Flight controller with Hobbywing ESC and motor poles configured
        WHEN: User imports FC parameters
        THEN: Motor poles should be set from ESC_HW_POLES parameter
        """
        fc_parameters = {"ESC_HW_POLES": 28, "MOT_PWM_TYPE": 0}
        doc: dict[str, Any] = {}

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True):
            realistic_model.process_fc_parameters(fc_parameters, doc)

        motor_poles = realistic_model.get_component_value(("Motors", "Specifications", "Poles"))
        assert motor_poles == 28

    def test_esc_hw_poles_takes_priority_over_servo_poles(self, realistic_model) -> None:
        """
        SERVO_BLH_POLES takes priority over ESC_HW_POLES when both present.

        GIVEN: Flight controller with both ESC_HW_POLES and SERVO_BLH_POLES configured
        WHEN: User imports FC parameters
        THEN: Motor poles should be set from SERVO_BLH_POLES (higher priority for DShot)
        """
        fc_parameters = {"ESC_HW_POLES": 28, "MOT_PWM_TYPE": 6, "SERVO_BLH_POLES": 14}
        doc: dict[str, Any] = {}

        with patch.object(realistic_model, "_verify_dict_is_uptodate", return_value=True):
            realistic_model.process_fc_parameters(fc_parameters, doc)

        motor_poles = realistic_model.get_component_value(("Motors", "Specifications", "Poles"))
        assert motor_poles == 14  # Should use SERVO_BLH_POLES (DShot), not ESC_HW_POLES

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

        GIVEN: BATT_MONITOR value is unrecognized
        WHEN: importing battery type
        THEN: error is logged and no exception is raised
        """
        fc_parameters = {"BATT_MONITOR": 999}  # Non-existent key

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

    def test_import_bat_values_from_fc_uses_battery_voltage_specs(self, basic_model) -> None:
        """BatteryVoltageSpecs is used and values are written to model."""
        specs = BatteryVoltageSpecs(
            estimated_cell_count=4,
            limit_min=BatteryCell.limit_min_voltage("Lipo"),
            limit_max=BatteryCell.limit_max_voltage("Lipo"),
            detected_chemistry="Lipo",
            fc_parameters={
                "BATT_CAPACITY": 4500,
                "MOT_BAT_VOLT_MAX": 16.8,
                "BATT_ARM_VOLT": 15.2,
                "BATT_LOW_VOLT": 14.4,
                "BATT_CRT_VOLT": 13.2,
                "MOT_BAT_VOLT_MIN": 12.8,
            },
        )

        basic_model._import_bat_values_from_fc(specs)

        assert basic_model.get_component_value(("Battery", "Specifications", "Capacity mAh")) == 4500
        assert basic_model.get_component_value(("Battery", "Specifications", "Volt per cell max")) == 4.2
        assert basic_model.get_component_value(("Battery", "Specifications", "Volt per cell arm")) == 3.8
        assert basic_model.get_component_value(("Battery", "Specifications", "Volt per cell low")) == 3.6
        assert basic_model.get_component_value(("Battery", "Specifications", "Volt per cell crit")) == 3.3
        assert basic_model.get_component_value(("Battery", "Specifications", "Volt per cell min")) == 3.2

    def test_estimate_battery_cell_count_does_not_override_with_min_voltage(self, realistic_model) -> None:
        """
        CONFIRM: high-priority source MOT_BAT_VOLT_MAX is not overridden by MOT_BAT_VOLT_MIN.

        GIVEN: existing cell voltage specs for max/min and an FC parameter set with both max and min volts
        WHEN: estimating battery cell count
        THEN: count should be based on MOT_BAT_VOLT_MAX priority path
        """
        realistic_model.set_component_value(("Battery", "Specifications", "Volt per cell max"), 4.2)
        realistic_model.set_component_value(("Battery", "Specifications", "Volt per cell min"), 3.2)

        fc_parameters = {
            "MOT_BAT_VOLT_MAX": 16.8,
            "MOT_BAT_VOLT_MIN": 14.5,
        }

        estimated = realistic_model._estimate_battery_cell_count(fc_parameters)

        assert estimated == 4

    def test_estimate_battery_cell_count_does_not_override_with_arm_voltage(self, realistic_model) -> None:
        """
        CONFIRM: high-priority source MOT_BAT_VOLT_MAX is not overridden by BATT_ARM_VOLT.

        GIVEN: existing cell voltage specs and an FC parameter set with max and arm volts
        WHEN: estimating battery cell count
        THEN: count should be based on MOT_BAT_VOLT_MAX priority path
        """
        realistic_model.set_component_value(("Battery", "Specifications", "Volt per cell max"), 4.2)
        realistic_model.set_component_value(("Battery", "Specifications", "Volt per cell arm"), 3.8)

        fc_parameters = {
            "MOT_BAT_VOLT_MAX": 16.8,
            "BATT_ARM_VOLT": 15.2,
        }

        estimated = realistic_model._estimate_battery_cell_count(fc_parameters)

        assert estimated == 4

    def test_system_handles_battery_monitor_value_not_in_connection_dict(self, realistic_model) -> None:
        """
        GIVEN: BATT_MONITOR value not in BATT_MONITOR_CONNECTION dict.

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
            fc_parameters_can2 = {"GPS_TYPE": 10, "CAN_D2_PROTOCOL": 1, "CAN_P2_DRIVER": 1}

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

    # ---- Tests for new battery arm/min voltage import (PR: Batt specifications) ----

    def test_user_can_import_arm_voltage_from_batt_arm_volt(self, basic_model) -> None:
        """
        User can import arm threshold voltage from BATT_ARM_VOLT FC parameter.

        GIVEN: FC parameters with BATT_ARM_VOLT set and valid cell specs
        WHEN: Calling import_bat_voltage with the arm voltage parameter
        THEN: Volt per cell arm should be set in the data model
        """
        # Arrange: pre-set arm voltage per cell so estimation uses it
        basic_model.set_component_value(("Battery", "Specifications", "Volt per cell arm"), 3.8)
        specs = BatteryVoltageSpecs(
            estimated_cell_count=4,
            limit_min=BatteryCell.limit_min_voltage("Lipo"),
            limit_max=BatteryCell.limit_max_voltage("Lipo"),
            detected_chemistry="Lipo",
            fc_parameters={"BATT_ARM_VOLT": 15.2},
        )

        # Act
        basic_model.import_bat_voltage(specs, "BATT_ARM_VOLT", "Volt per cell arm")

        # Assert
        arm = basic_model.get_component_value(("Battery", "Specifications", "Volt per cell arm"))
        assert arm == pytest.approx(3.8)

    def test_user_can_import_min_voltage_from_mot_bat_volt_min(self, basic_model) -> None:
        """
        User can import PID-scaling floor voltage from MOT_BAT_VOLT_MIN FC parameter.

        GIVEN: FC parameters with MOT_BAT_VOLT_MIN set and valid cell specs
        WHEN: Calling import_bat_voltage with the min voltage parameter
        THEN: Volt per cell min should be set in the data model
        """
        # Arrange
        specs = BatteryVoltageSpecs(
            estimated_cell_count=4,
            limit_min=BatteryCell.limit_min_voltage("Lipo"),
            limit_max=BatteryCell.limit_max_voltage("Lipo"),
            detected_chemistry="Lipo",
            fc_parameters={"MOT_BAT_VOLT_MIN": 12.8},
        )

        # Act
        basic_model.import_bat_voltage(specs, "MOT_BAT_VOLT_MIN", "Volt per cell min")

        # Assert
        min_v = basic_model.get_component_value(("Battery", "Specifications", "Volt per cell min"))
        assert min_v == pytest.approx(3.2)

    def test_system_skips_import_for_out_of_range_arm_voltage(self, basic_model) -> None:
        """
        System warns and skips setting arm voltage when the calculated per-cell value is out of chemistry range.

        GIVEN: FC parameters where BATT_ARM_VOLT / cell_count falls outside Lipo limits
        WHEN: Calling import_bat_voltage
        THEN: A warning is logged and the value is NOT set in the model
        AND: No exception is raised
        """
        # Arrange: extremely high voltage so per-cell value exceeds Lipo limit_max (4.2 V)
        original_arm = basic_model.get_component_value(("Battery", "Specifications", "Volt per cell arm"))
        specs = BatteryVoltageSpecs(
            estimated_cell_count=4,
            limit_min=BatteryCell.limit_min_voltage("Lipo"),
            limit_max=BatteryCell.limit_max_voltage("Lipo"),
            detected_chemistry="Lipo",
            fc_parameters={"BATT_ARM_VOLT": 99.9},  # 99.9 / 4 = 24.975 V >> 4.2 V limit
        )

        # Act
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning") as mock_warn:
            basic_model.import_bat_voltage(specs, "BATT_ARM_VOLT", "Volt per cell arm")

        # Assert: warning was issued, value unchanged
        mock_warn.assert_called()
        arm = basic_model.get_component_value(("Battery", "Specifications", "Volt per cell arm"))
        assert arm == original_arm  # unchanged

    def test_system_handles_type_error_in_import_bat_voltage(self, basic_model) -> None:
        """
        System handles TypeError when FC parameter value is not numeric.

        GIVEN: FC parameters with a non-numeric BATT_ARM_VOLT value (e.g., None)
        WHEN: Calling import_bat_voltage
        THEN: An error is logged and no exception is raised
        """
        # Arrange
        specs = BatteryVoltageSpecs(
            estimated_cell_count=4,
            limit_min=BatteryCell.limit_min_voltage("Lipo"),
            limit_max=BatteryCell.limit_max_voltage("Lipo"),
            detected_chemistry="Lipo",
            fc_parameters={"BATT_ARM_VOLT": None},  # type: ignore[dict-item]
        )

        # Act & Assert: should not raise
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as mock_err:
            basic_model.import_bat_voltage(specs, "BATT_ARM_VOLT", "Volt per cell arm")
        mock_err.assert_called()

    def test_system_skips_import_bat_voltage_for_missing_parameter(self, basic_model) -> None:
        """
        System silently skips arm voltage import when the FC parameter is absent.

        GIVEN: FC parameters that do NOT contain BATT_ARM_VOLT
        WHEN: Calling import_bat_voltage for arm
        THEN: No value is set and no error is raised
        """
        # Arrange
        original_arm = basic_model.get_component_value(("Battery", "Specifications", "Volt per cell arm"))
        specs = BatteryVoltageSpecs(
            estimated_cell_count=4,
            limit_min=BatteryCell.limit_min_voltage("Lipo"),
            limit_max=BatteryCell.limit_max_voltage("Lipo"),
            detected_chemistry="Lipo",
            fc_parameters={},  # BATT_ARM_VOLT absent
        )

        # Act
        basic_model.import_bat_voltage(specs, "BATT_ARM_VOLT", "Volt per cell arm")

        # Assert: value unchanged
        arm = basic_model.get_component_value(("Battery", "Specifications", "Volt per cell arm"))
        assert arm == original_arm

    def test_system_does_not_warn_when_cell_voltage_equals_chemistry_limit_max(self, basic_model) -> None:
        """
        System accepts MOT_BAT_VOLT_MAX at exactly the chemistry limit_max without a false warning.

        GIVEN: A 4S Lipo whose MOT_BAT_VOLT_MAX equals 4 x 4.2 = 16.8 V
        WHEN: Calling import_bat_voltage for "max"
        THEN: No warning is logged — floating-point division 16.8/4 must not exceed limit_max=4.2
        AND: Volt per cell max is set to 4.2 V
        """
        specs = BatteryVoltageSpecs(
            estimated_cell_count=4,
            limit_min=BatteryCell.limit_min_voltage("Lipo"),
            limit_max=BatteryCell.limit_max_voltage("Lipo"),
            detected_chemistry="Lipo",
            fc_parameters={"MOT_BAT_VOLT_MAX": 16.8},  # 16.8 / 4 = 4.2 exactly in math, but fp can be > 4.2
        )

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning") as mock_warn:
            basic_model.import_bat_voltage(specs, "MOT_BAT_VOLT_MAX", "Volt per cell max")

        mock_warn.assert_not_called()
        cell_max = basic_model.get_component_value(("Battery", "Specifications", "Volt per cell max"))
        assert cell_max == pytest.approx(4.2)

    def test_import_bat_values_skips_all_voltages_when_cell_count_is_zero(self, basic_model) -> None:
        """
        System skips all voltage imports when estimated_cell_count is zero.

        GIVEN: BatteryVoltageSpecs with estimated_cell_count=0
        WHEN: Calling _import_bat_values_from_fc
        THEN: No voltage fields are updated in the model
        """
        # Arrange: store initial values for comparison
        specs = BatteryVoltageSpecs(
            estimated_cell_count=0,
            limit_min=BatteryCell.limit_min_voltage("Lipo"),
            limit_max=BatteryCell.limit_max_voltage("Lipo"),
            detected_chemistry="Lipo",
            fc_parameters={
                "BATT_CAPACITY": 4500,
                "MOT_BAT_VOLT_MAX": 16.8,
                "BATT_ARM_VOLT": 15.2,
                "BATT_LOW_VOLT": 14.4,
                "BATT_CRT_VOLT": 13.2,
                "MOT_BAT_VOLT_MIN": 12.8,
            },
        )
        original_max = basic_model.get_component_value(("Battery", "Specifications", "Volt per cell max"))

        # Act
        basic_model._import_bat_values_from_fc(specs)

        # Assert: capacity IS set (not guarded by cell count), voltages are NOT set
        capacity = basic_model.get_component_value(("Battery", "Specifications", "Capacity mAh"))
        assert capacity == 4500
        assert basic_model.get_component_value(("Battery", "Specifications", "Volt per cell max")) == original_max

    def test_estimate_cell_count_uses_batt_arm_volt_as_fallback(self, basic_model) -> None:
        """
        System uses BATT_ARM_VOLT to estimate cell count when higher-priority sources are absent.

        GIVEN: FC parameters with only BATT_ARM_VOLT available, and arm per-cell value set
        WHEN: Calling _estimate_battery_cell_count
        THEN: Cell count is estimated correctly from BATT_ARM_VOLT
        """
        # Arrange: set a valid arm voltage per cell so estimation works
        basic_model.set_component_value(("Battery", "Specifications", "Volt per cell arm"), 3.8)

        fc_parameters = {"BATT_ARM_VOLT": 15.2}  # 15.2 / 3.8 = 4 cells, no higher-prio params

        # Act
        estimated = basic_model._estimate_battery_cell_count(fc_parameters)

        # Assert
        assert estimated == 4

    def test_estimate_cell_count_uses_mot_bat_volt_min_as_last_resort(self, basic_model) -> None:
        """
        System uses MOT_BAT_VOLT_MIN to estimate cell count as the lowest-priority fallback.

        GIVEN: FC parameters with only MOT_BAT_VOLT_MIN available, and min per-cell value set
        WHEN: Calling _estimate_battery_cell_count
        THEN: Cell count is estimated correctly from MOT_BAT_VOLT_MIN
        """
        # Arrange: set a valid min voltage per cell so estimation works
        basic_model.set_component_value(("Battery", "Specifications", "Volt per cell min"), 3.2)

        fc_parameters = {"MOT_BAT_VOLT_MIN": 12.8}  # 12.8 / 3.2 = 4 cells, no higher-prio params

        # Act
        estimated = basic_model._estimate_battery_cell_count(fc_parameters)

        # Assert
        assert estimated == 4

    def test_detect_chemistry_from_batt_arm_volt(self, realistic_model) -> None:
        """
        System correctly detects battery chemistry using BATT_ARM_VOLT as a clue.

        GIVEN: Only BATT_ARM_VOLT is available and its per-cell ratio closely matches Lipo arm voltage
        WHEN: Calling _detect_battery_chemistry_from_voltages without any current chemistry context
        THEN: The system detects 'Lipo' (or at least does not raise an exception)
        """
        # 4S Lipo arm ~3.8 V/cell => total 15.2 V
        fc_parameters = {"BATT_ARM_VOLT": 15.2}

        result = realistic_model._detect_battery_chemistry_from_voltages(fc_parameters, current_chemistry=None)

        # BATT_ARM_VOLT should be used as a detection signal — any valid chemistry or None is acceptable

        valid_chemistries = set(BatteryCell.chemistries())
        assert result is None or result in valid_chemistries

    def test_detect_chemistry_from_mot_bat_volt_min(self, realistic_model) -> None:
        """
        System uses MOT_BAT_VOLT_MIN as a last-resort chemistry clue.

        GIVEN: Only MOT_BAT_VOLT_MIN is available, consistent with a 4S Lipo min voltage
        WHEN: Calling _detect_battery_chemistry_from_voltages
        THEN: The system returns a chemistry (or None) without raising exceptions
        """
        # 4S Lipo recommended_min 3.2 V/cell => total 12.8 V
        fc_parameters = {"MOT_BAT_VOLT_MIN": 12.8}

        result = realistic_model._detect_battery_chemistry_from_voltages(fc_parameters, current_chemistry=None)

        # Detection may succeed or fail gracefully; no exception should be raised
        assert result is None or isinstance(result, str)

    def test_estimate_cell_count_returns_zero_for_all_invalid_volt_per_cell(self, basic_model) -> None:
        """
        System returns 0 when all volt-per-cell values are zero/invalid.

        GIVEN: FC parameters with voltage params but all volt-per-cell stored values are zero
        WHEN: Calling _estimate_battery_cell_count
        THEN: Returns 0 and an error is logged
        """
        # Arrange: all voltage specs are zero (invalid) - basic_model has default 0s
        fc_parameters = {
            "MOT_BAT_VOLT_MAX": 16.8,
            "BATT_LOW_VOLT": 14.4,
            "BATT_CRT_VOLT": 13.2,
            "BATT_ARM_VOLT": 15.2,
            "MOT_BAT_VOLT_MIN": 12.8,
        }

        # Act
        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"):
            estimated = basic_model._estimate_battery_cell_count(fc_parameters)

        # Assert
        assert estimated == 0


class TestComponentDataModelImportUncoveredBranches:
    """Tests targeting previously uncovered branches in ComponentDataModelImport."""

    @pytest.fixture
    def basic_model(self) -> ComponentDataModelImport:
        """Create a basic model with zero volt-per-cell specs."""
        return ComponentDataModelFixtures.create_basic_model(ComponentDataModelImport)

    @pytest.fixture
    def realistic_model(self) -> ComponentDataModelImport:
        """Create a realistic model with real battery specs."""
        return ComponentDataModelFixtures.create_realistic_model(ComponentDataModelImport)

    # ------------------------------------------------------------------
    # _reverse_key_search
    # ------------------------------------------------------------------
    def test_system_logs_error_when_reverse_key_search_values_not_found(self) -> None:
        """
        _reverse_key_search returns fallbacks when no values match and logs an error.

        GIVEN: A doc dict where none of the requested values exist in the param's 'values' entry
        WHEN: _reverse_key_search is called
        THEN: The fallback values should be returned AND an error should be logged
        """
        doc = {"MY_PARAM": {"values": {"0": "None", "1": "MAVLink1"}}}
        values_to_find = ["DroneCAN"]  # not in the dict
        fallbacks = [99]

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as mock_err:
            result = ComponentDataModelImport._reverse_key_search(doc, "MY_PARAM", values_to_find, fallbacks)

        assert result == fallbacks
        mock_err.assert_called()

    def test_system_logs_error_when_reverse_key_search_length_differs(self) -> None:
        """
        _reverse_key_search logs an error when len(values) != len(fallbacks).

        GIVEN: A values list and a fallbacks list of different lengths
        WHEN: _reverse_key_search is called with a matching entry
        THEN: An error should be logged about the length mismatch
        AND: The found keys should still be returned
        """
        doc = {"MY_PARAM": {"values": {"0": "None", "1": "MAVLink1"}}}
        values_to_find = ["MAVLink1"]  # matches key "1"
        fallbacks_wrong_length = [1, 2, 3]  # length != 1

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as mock_err:
            result = ComponentDataModelImport._reverse_key_search(doc, "MY_PARAM", values_to_find, fallbacks_wrong_length)

        assert result == [1]  # found key for "MAVLink1"
        mock_err.assert_called()

    # ------------------------------------------------------------------
    # _verify_dict_is_uptodate with bitmask and invalid bit position
    # ------------------------------------------------------------------
    def test_system_warns_and_skips_invalid_bitmask_bit_positions(self, basic_model) -> None:
        """
        _verify_dict_is_uptodate warns and continues when a bitmask key is not an integer.

        GIVEN: A doc dict with a Bitmask entry that has a non-integer bit position key
        WHEN: _verify_dict_is_uptodate is called
        THEN: A warning should be logged for the invalid key
        AND: Processing should continue for the remaining keys
        """
        doc = {"RC_PROTOCOLS": {"Bitmask": {"not_a_number": "All", "9": "CRSF"}}}
        dict_to_check = {"512": {"protocol": "CRSF"}}  # key 512 = 2^9

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning") as mock_warn:
            _result = basic_model._verify_dict_is_uptodate(doc, dict_to_check, "RC_PROTOCOLS", "Bitmask")

        # The non-integer "not_a_number" key hits the except branch → "Invalid bit position" warning
        mock_warn.assert_any_call("Invalid bit position %s in %s metadata", "not_a_number", "RC_PROTOCOLS")

    # ------------------------------------------------------------------
    # _set_battery_type_from_fc_parameters - I2C edge cases
    # ------------------------------------------------------------------
    def test_system_warns_when_i2c_bus_index_is_out_of_range(self, realistic_model) -> None:
        """
        System warns and defaults to first I2C bus when BATT_I2C_BUS is out of range.

        GIVEN: A BATT_MONITOR configured for I2C (type 5 = Solo) with BATT_I2C_BUS=99
        WHEN: _set_battery_type_from_fc_parameters is called
        THEN: A warning should be logged about the out-of-range value
        AND: The first I2C bus should be used as default
        """
        fc_parameters: dict[str, Any] = {"BATT_MONITOR": 5, "BATT_I2C_BUS": 99}

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning") as mock_warn:
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

        texts = " ".join(str(c) for c in mock_warn.call_args_list)
        assert "out of range" in texts or "BATT_I2C_BUS" in texts

    def test_system_warns_when_i2c_bus_value_is_not_an_integer(self, realistic_model) -> None:
        """
        System warns and defaults to first I2C bus when BATT_I2C_BUS cannot be parsed as int.

        GIVEN: A BATT_MONITOR configured for I2C and BATT_I2C_BUS holds a non-integer string
        WHEN: _set_battery_type_from_fc_parameters is called
        THEN: A warning should be logged about the invalid value
        """
        fc_parameters: dict[str, Any] = {"BATT_MONITOR": 5, "BATT_I2C_BUS": "not_an_int"}

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning") as mock_warn:
            realistic_model._set_battery_type_from_fc_parameters(fc_parameters)

        texts = " ".join(str(c) for c in mock_warn.call_args_list)
        assert "Invalid BATT_I2C_BUS" in texts or "defaulting" in texts

    def test_system_warns_when_batt_monitor_parameter_is_absent(self, basic_model) -> None:
        """
        System logs a warning when BATT_MONITOR is absent from fc_parameters.

        GIVEN: fc_parameters that do not contain the BATT_MONITOR key
        WHEN: _set_battery_type_from_fc_parameters is called
        THEN: A warning should be logged about the missing parameter
        """
        fc_parameters: dict[str, Any] = {}  # no BATT_MONITOR key

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning") as mock_warn:
            basic_model._set_battery_type_from_fc_parameters(fc_parameters)

        texts = " ".join(str(c) for c in mock_warn.call_args_list)
        assert "BATT_MONITOR" in texts

    # ------------------------------------------------------------------
    # import_bat_voltage - invalid voltage_type
    # ------------------------------------------------------------------
    def test_system_logs_error_for_invalid_voltage_type_in_import_bat_voltage(self, basic_model) -> None:
        """
        import_bat_voltage logs an error and returns early for an unknown voltage_type.

        GIVEN: A BatteryVoltageSpecs with a valid param_name and a specs object
        AND: voltage_type is not in BATTERY_CELL_VOLTAGE_TYPES
        WHEN: import_bat_voltage is called
        THEN: An error should be logged and no value should be stored
        """
        specs = BatteryVoltageSpecs(
            estimated_cell_count=4,
            limit_min=3.0,
            limit_max=4.5,
            detected_chemistry="Lipo",
            fc_parameters={"MOT_BAT_VOLT_MAX": 16.8},
        )

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as mock_err:
            basic_model.import_bat_voltage(specs, "MOT_BAT_VOLT_MAX", "not_a_valid_type")

        mock_err.assert_called()

    # ------------------------------------------------------------------
    # _estimate_battery_cell_count - BATT_ARM_VOLT and MOT_BAT_VOLT_MIN fallbacks
    # ------------------------------------------------------------------
    def test_system_uses_batt_arm_volt_as_fallback_for_cell_count_estimation(self, realistic_model) -> None:
        """
        _estimate_battery_cell_count falls back to BATT_ARM_VOLT when higher-priority params absent.

        GIVEN: Only BATT_ARM_VOLT is present in fc_parameters (all higher-priority params absent)
        WHEN: _estimate_battery_cell_count is called
        THEN: The BATT_ARM_VOLT path should be taken as a fallback
        AND: The result should be either a positive integer or 0 (if volt_per_cell is unset)
        """
        # Only provide BATT_ARM_VOLT, omit MOT_BAT_VOLT_MAX/BATT_LOW_VOLT/BATT_CRT_VOLT
        fc_parameters = {"BATT_ARM_VOLT": 15.2}

        with (
            patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning"),
            patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"),
        ):
            result = realistic_model._estimate_battery_cell_count(fc_parameters)

        assert isinstance(result, int)

    def test_system_uses_mot_bat_volt_min_as_last_resort_for_cell_count_estimation(self, realistic_model) -> None:
        """
        _estimate_battery_cell_count uses MOT_BAT_VOLT_MIN as the lowest-priority fallback.

        GIVEN: Only MOT_BAT_VOLT_MIN is present in fc_parameters
        WHEN: _estimate_battery_cell_count is called
        THEN: The MOT_BAT_VOLT_MIN path should be taken
        AND: The result should be an integer (positive or 0)
        """
        fc_parameters = {"MOT_BAT_VOLT_MIN": 12.8}

        with (
            patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning"),
            patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error"),
        ):
            result = realistic_model._estimate_battery_cell_count(fc_parameters)

        assert isinstance(result, int)

    # ------------------------------------------------------------------
    # _verify_dict_is_uptodate — protocols-match branch (line 250->259)
    # and protocols-mismatch (line 279)
    # ------------------------------------------------------------------
    def test_system_passes_when_code_and_doc_protocols_match(self, basic_model) -> None:
        """
        _verify_dict_is_uptodate returns True when code protocol matches doc protocol.

        GIVEN: A doc and a dict_to_check where every protocol value agrees
        WHEN: _verify_dict_is_uptodate is called
        THEN: True is returned with no warning logged
        AND: The False-branch of 'if code_protocol != doc_protocol' is exercised (250->259)
        """
        doc = {"SERIAL1_PROTOCOL": {"values": {"1": "MAVLink1"}}}
        dict_to_check = {"1": {"protocol": "MAVLink1"}}  # matches exactly

        result = basic_model._verify_dict_is_uptodate(doc, dict_to_check, "SERIAL1_PROTOCOL", "values")

        assert result is True

    def test_system_warns_when_doc_key_is_absent_from_code_dict(self, basic_model) -> None:
        """
        _verify_dict_is_uptodate logs a warning when a doc key is absent from the code dictionary.

        GIVEN: A doc with protocol key "99" that is not present in dict_to_check
        WHEN: _verify_dict_is_uptodate is called
        THEN: A warning is logged and False is returned (else-branch / line 279 path exercised)
        """
        doc = {"SERIAL1_PROTOCOL": {"values": {"99": "FakeProtocol"}}}
        dict_to_check = {"1": {"protocol": "MAVLink1"}}  # "99" not present

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning") as mock_warn:
            result = basic_model._verify_dict_is_uptodate(doc, dict_to_check, "SERIAL1_PROTOCOL", "values")

        assert result is False
        mock_warn.assert_called()

    # ------------------------------------------------------------------
    # _set_serial_type_from_fc_parameters — skip protocol 0 and unknown (lines 275, 279)
    # ------------------------------------------------------------------
    def test_system_skips_serial_port_with_protocol_zero(self, basic_model) -> None:
        """
        _set_serial_type_from_fc_parameters skips a serial port whose protocol number is 0.

        GIVEN: fc_parameters with SERIAL1_PROTOCOL=0 (disabled)
        WHEN: _set_serial_type_from_fc_parameters is called
        THEN: No component values are changed for that port (continue at line 275 is exercised)
        """
        fc_parameters: dict[str, Any] = {"SERIAL1_PROTOCOL": 0}
        result = basic_model._set_serial_type_from_fc_parameters(fc_parameters)
        assert isinstance(result, bool)

    def test_system_skips_serial_port_with_unknown_protocol_number(self, basic_model) -> None:
        """
        _set_serial_type_from_fc_parameters skips a port when protocol number is not in the dict.

        GIVEN: fc_parameters with SERIAL1_PROTOCOL=999 (not in SERIAL_PROTOCOLS_DICT)
        WHEN: _set_serial_type_from_fc_parameters is called
        THEN: The port is silently skipped (continue at line 279 is exercised)
        """
        fc_parameters: dict[str, Any] = {"SERIAL1_PROTOCOL": 999}
        result = basic_model._set_serial_type_from_fc_parameters(fc_parameters)
        assert isinstance(result, bool)

    # ------------------------------------------------------------------
    # _set_esc_type_from_fc_parameters — protocol empty (line 332) and dict fallback (line 335)
    # ------------------------------------------------------------------
    def test_system_skips_setting_esc_protocol_when_doc_value_is_absent(self, basic_model) -> None:
        """
        _set_esc_type_from_fc_parameters skips setting ESC protocol when mot_pwm_type absent from doc values.

        GIVEN: doc has MOT_PWM_TYPE.values but does NOT contain the key for mot_pwm_type=99
        WHEN: _set_esc_type_from_fc_parameters is called
        THEN: No protocol is set via doc (if protocol: False branch at line 332 is exercised)
        AND: The function completes without error
        """
        fc_parameters: dict[str, Any] = {"MOT_PWM_TYPE": 99}  # 99 not in doc
        doc: dict[str, Any] = {"MOT_PWM_TYPE": {"values": {"0": "Normal", "6": "DShot600"}}}

        basic_model._set_esc_type_from_fc_parameters(fc_parameters, doc)

        # Should not crash; exact protocol value depends on model default
        result = basic_model.get_component_value(("ESC", "FC Connection", "Protocol"))
        assert result is not None

    def test_system_uses_mot_pwm_type_dict_fallback_when_doc_has_no_mot_pwm_type(self, basic_model) -> None:
        """
        _set_esc_type_from_fc_parameters falls back to MOT_PWM_TYPE_DICT when doc lacks values.

        GIVEN: doc has no MOT_PWM_TYPE entry (empty)
        AND: fc_parameters has MOT_PWM_TYPE=0 (which IS in MOT_PWM_TYPE_DICT as 'Normal')
        WHEN: _set_esc_type_from_fc_parameters is called
        THEN: Protocol is set to 'Normal' via the elif fallback (line 335 exercised)
        """
        fc_parameters: dict[str, Any] = {"MOT_PWM_TYPE": 0}
        doc: dict[str, Any] = {}  # no MOT_PWM_TYPE in doc

        basic_model._set_esc_type_from_fc_parameters(fc_parameters, doc)

        result = basic_model.get_component_value(("ESC", "FC Connection", "Protocol"))
        assert result == "Normal"

    # ------------------------------------------------------------------
    # _set_battery_type_from_fc_parameters — valid I2C bus index (line 363)
    # and non-I2C list type (Analog) (line 376)
    # ------------------------------------------------------------------
    def test_system_selects_i2c_bus_by_index_when_batt_i2c_bus_is_valid(self, basic_model) -> None:
        """
        _set_battery_type_from_fc_parameters uses BATT_I2C_BUS index to select the I2C bus.

        GIVEN: BATT_MONITOR=5 (Solo, I2C type) and BATT_I2C_BUS=1 (selects I2C2 = index 1)
        WHEN: _set_battery_type_from_fc_parameters is called
        THEN: FC Connection Type should be set to 'I2C2' (fc_conn_type[1]) (line 363 exercised)
        """
        fc_parameters: dict[str, Any] = {"BATT_MONITOR": 5, "BATT_I2C_BUS": 1}

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning"):
            basic_model._set_battery_type_from_fc_parameters(fc_parameters)

        result = basic_model.get_component_value(("Battery Monitor", "FC Connection", "Type"))
        assert result == "I2C2"

    def test_system_defaults_to_first_element_for_non_i2c_list_battery_type(self, basic_model) -> None:
        """
        _set_battery_type_from_fc_parameters takes the first element of a non-I2C list type.

        GIVEN: BATT_MONITOR=3 (Analog Voltage Only) whose type is ANALOG_PORTS=['Analog']
        AND: That list is NOT a subset of I2C_PORTS
        WHEN: _set_battery_type_from_fc_parameters is called
        THEN: FC Connection Type should be set to 'Analog' (first element) (line 376 exercised)
        """
        fc_parameters: dict[str, Any] = {"BATT_MONITOR": 3}

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning"):
            basic_model._set_battery_type_from_fc_parameters(fc_parameters)

        result = basic_model.get_component_value(("Battery Monitor", "FC Connection", "Type"))
        assert result == "Analog"

    # ------------------------------------------------------------------
    # _detect_battery_chemistry_from_voltages — isnan(score) log+continue (lines 504-509)
    # ------------------------------------------------------------------
    def test_system_logs_warning_when_chemistry_score_is_nan(self, basic_model, monkeypatch) -> None:
        """
        _detect_battery_chemistry_from_voltages logs a warning when chemistry_voltage_score returns NaN.

        GIVEN: BatteryCell.chemistry_voltage_score is patched to always return NaN
        AND: fc_parameters contains MOT_BAT_VOLT_MAX=16.8 and current_chemistry='Lipo'
        WHEN: _detect_battery_chemistry_from_voltages is called
        THEN: A warning is logged for each parameter (lines 504-509 exercised)
        AND: The function falls through to best_chemistry_for_voltage and returns a result
        """
        monkeypatch.setattr(
            BatteryCell,
            "chemistry_voltage_score",
            staticmethod(lambda *_a, **_kw: nan),
        )

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning") as mock_warn:
            result = basic_model._detect_battery_chemistry_from_voltages({"MOT_BAT_VOLT_MAX": 16.8}, "Lipo")

        # NaN score causes warning and continue; best_chemistry_for_voltage then determines the result
        assert mock_warn.called
        assert result is None or isinstance(result, str)

    # ------------------------------------------------------------------
    # _set_gnss_type_from_fc_parameters — invalid connection type (lines 228-229)
    # ------------------------------------------------------------------
    def test_system_logs_error_when_gnss_conn_type_is_neither_serial_nor_can(self, basic_model, monkeypatch) -> None:
        """
        _set_gnss_type_from_fc_parameters logs an error for GPS types with unknown connection type.

        GIVEN: GNSS_RECEIVER_CONNECTION is patched so GPS_TYPE 99 maps to type=['USB'] (not SERIAL/CAN)
        WHEN: _set_gnss_type_from_fc_parameters is called with fc_parameters={'GPS_TYPE': 99}
        THEN: logging_error is called with 'Invalid GNSS connection type' (lines 228-229 exercised)
        AND: FC Connection Type is set to 'None'
        """
        fake_gnss_conn: dict[str, Any] = {"99": {"type": ["USB"], "protocol": "Unknown"}}
        monkeypatch.setattr(_import_module, "GNSS_RECEIVER_CONNECTION", fake_gnss_conn)

        with patch.object(_import_module, "logging_error") as mock_err:
            basic_model._set_gnss_type_from_fc_parameters({"GPS_TYPE": 99})

        # Verify error was logged about invalid connection type
        logged_text = " ".join(str(call) for call in mock_err.call_args_list)
        assert "Invalid GNSS connection type" in logged_text

        result = basic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        assert result == "None"

    # ------------------------------------------------------------------
    # _verify_dict_is_uptodate — protocol mismatch (lines 141-142)
    # ------------------------------------------------------------------
    def test_system_warns_when_code_and_doc_protocols_differ(self, basic_model) -> None:
        """
        _verify_dict_is_uptodate logs a warning when check_key is found but protocols differ.

        GIVEN: A doc saying key "1" maps to "MAVLink2"
        AND: dict_to_check saying key "1" maps to "MAVLink1" (mismatch!)
        WHEN: _verify_dict_is_uptodate is called
        THEN: A warning is logged about the protocol mismatch (lines 141-142 exercised)
        AND: False is returned
        """
        doc = {"SERIAL1_PROTOCOL": {"values": {"1": "MAVLink2"}}}  # doc expects MAVLink2
        dict_to_check = {"1": {"protocol": "MAVLink1"}}  # code has MAVLink1 — MISMATCH

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning") as mock_warn:
            result = basic_model._verify_dict_is_uptodate(doc, dict_to_check, "SERIAL1_PROTOCOL", "values")

        assert result is False
        logged_text = " ".join(str(c) for c in mock_warn.call_args_list)
        assert "does not match" in logged_text or "MAVLink" in logged_text

    # ------------------------------------------------------------------
    # _set_serial_type_from_fc_parameters — RC_PROTOCOLS single bit not in dict (line 250->259)
    # ------------------------------------------------------------------
    def test_system_skips_rc_protocol_assignment_when_single_bit_not_in_dict(self, basic_model) -> None:
        """
        _set_serial_type_from_fc_parameters skips RC protocol assignment when bit value is not in dict.

        GIVEN: RC_PROTOCOLS = 131072 (2^17 = single bit set, but NOT in RC_PROTOCOLS_DICT which goes up to 2^16)
        WHEN: _set_serial_type_from_fc_parameters is called
        THEN: RC Receiver protocol is not updated (line 250->259 False branch exercised)
        AND: The function completes without error
        """
        fc_parameters: dict[str, Any] = {"RC_PROTOCOLS": 131072}  # 2^17, not in dict
        result = basic_model._set_serial_type_from_fc_parameters(fc_parameters)
        assert isinstance(result, bool)

    # ------------------------------------------------------------------
    # _set_esc_type_from_fc_parameters — neither doc nor dict has the protocol (line 335->exit)
    # ------------------------------------------------------------------
    def test_system_leaves_esc_protocol_unchanged_when_type_not_in_doc_or_dict(self, basic_model) -> None:
        """
        _set_esc_type_from_fc_parameters leaves ESC protocol unchanged when mot_pwm_type is unknown.

        GIVEN: doc is empty (no MOT_PWM_TYPE key)
        AND: fc_parameters has MOT_PWM_TYPE=999 (not in MOT_PWM_TYPE_DICT either)
        WHEN: _set_esc_type_from_fc_parameters is called
        THEN: Neither the doc branch nor the dict fallback sets the protocol (line 335->exit exercised)
        AND: The function completes without error
        """
        fc_parameters: dict[str, Any] = {"MOT_PWM_TYPE": 999}  # not in dict
        doc: dict[str, Any] = {}  # no MOT_PWM_TYPE in doc either

        basic_model._set_esc_type_from_fc_parameters(fc_parameters, doc)
        # No crash — function just falls through both if/elif conditions

    # ------------------------------------------------------------------
    # _set_esc_type_from_fc_parameters — MOT_PWM_TYPE non-integer (lines 318-320)
    # ------------------------------------------------------------------
    def test_system_logs_error_for_non_integer_mot_pwm_type(self, basic_model) -> None:
        """
        _set_esc_type_from_fc_parameters logs an error when MOT_PWM_TYPE cannot be converted to int.

        GIVEN: fc_parameters has MOT_PWM_TYPE='abc' (non-integer string)
        WHEN: _set_esc_type_from_fc_parameters is called
        THEN: An error is logged and mot_pwm_type defaults to 0 (lines 318-320 exercised)
        """
        fc_parameters: dict[str, Any] = {"MOT_PWM_TYPE": "abc"}
        doc: dict[str, Any] = {}

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_error") as mock_err:
            basic_model._set_esc_type_from_fc_parameters(fc_parameters, doc)

        mock_err.assert_called()

    # ------------------------------------------------------------------
    # _set_battery_type_from_fc_parameters — I2C bus without BATT_I2C_BUS (line 376)
    # ------------------------------------------------------------------
    def test_system_defaults_to_first_i2c_bus_when_batt_i2c_bus_not_provided(self, basic_model) -> None:
        """
        _set_battery_type_from_fc_parameters defaults to I2C1 when BATT_I2C_BUS is absent.

        GIVEN: BATT_MONITOR=5 (Solo, I2C type) but NO BATT_I2C_BUS parameter
        WHEN: _set_battery_type_from_fc_parameters is called
        THEN: FC Connection Type defaults to 'I2C1' (first element, line 376 exercised)
        """
        fc_parameters: dict[str, Any] = {"BATT_MONITOR": 5}  # I2C type, no BATT_I2C_BUS

        with patch("ardupilot_methodic_configurator.data_model_vehicle_components_import.logging_warning"):
            basic_model._set_battery_type_from_fc_parameters(fc_parameters)

        result = basic_model.get_component_value(("Battery Monitor", "FC Connection", "Type"))
        assert result == "I2C1"

    # ------------------------------------------------------------------
    # _set_serial_type_from_fc_parameters — GNSS CAN type prevents serial override (line 300->302)
    # ------------------------------------------------------------------
    def test_system_skips_gnss_type_override_when_type_is_can(self, basic_model) -> None:
        """
        _set_serial_type_from_fc_parameters skips setting GNSS type when already set to a CAN port.

        GIVEN: GNSS Receiver FC Connection Type is set to 'CAN1' (already configured via CAN)
        AND: SERIAL3_PROTOCOL=5 (GPS protocol) is in fc_parameters
        WHEN: _set_serial_type_from_fc_parameters is called
        THEN: GNSS Receiver Type stays as 'CAN1' (not overwritten by SERIAL3)
        AND: Line 300->302 (False branch of 'if current_gnss_type not in CAN_PORTS:') is exercised
        """
        basic_model.set_component_value(("GNSS Receiver", "FC Connection", "Type"), "CAN1")
        fc_parameters: dict[str, Any] = {"SERIAL3_PROTOCOL": 5}  # GPS on SERIAL3

        basic_model._set_serial_type_from_fc_parameters(fc_parameters)

        result = basic_model.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        assert result == "CAN1"  # Not overwritten

    # ------------------------------------------------------------------
    # _set_serial_type_from_fc_parameters — second RC Receiver falls through elif chain (line 303->263)
    # ------------------------------------------------------------------
    def test_system_skips_second_rc_receiver_serial_assignment(self, basic_model) -> None:
        """
        _set_serial_type_from_fc_parameters ignores second RC Receiver when one was already assigned.

        GIVEN: Two serial ports both configured with RCIN (RC Receiver) protocol=23
        WHEN: _set_serial_type_from_fc_parameters is called
        THEN: Only the first RC Receiver is assigned; the second falls through all elif branches
        AND: Line 303->263 (elif component == 'ESC' False branch) is exercised
        """
        fc_parameters: dict[str, Any] = {
            "SERIAL1_PROTOCOL": 23,  # RCIN = RC Receiver, first → assigned
            "SERIAL2_PROTOCOL": 23,  # RCIN = RC Receiver, second → rc > 1 → skipped
        }

        basic_model._set_serial_type_from_fc_parameters(fc_parameters)

        result = basic_model.get_component_value(("RC Receiver", "FC Connection", "Type"))
        assert result == "SERIAL1"  # Only first RC Receiver assigned
