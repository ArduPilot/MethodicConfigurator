#!/usr/bin/env python3

"""
Vehicle Components data model tests.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import pytest

from ardupilot_methodic_configurator.data_model_vehicle_components import ComponentDataModel

# pylint: disable=too-many-lines,protected-access,too-many-public-methods


class TestComponentDataModel:
    """Tests for the ComponentDataModel class."""

    @pytest.fixture
    def component_data_model(self) -> ComponentDataModel:
        """Create a ComponentDataModel fixture for testing."""
        initial_data = {
            "Components": {
                "Motor": {"Type": "brushless", "KV": 1000, "Configuration": {"Wiring": "star"}},
                "ESC": {"Current": 30},
            },
            "Format version": 2,
        }
        return ComponentDataModel(initial_data)

    @pytest.fixture
    def empty_data_model(self) -> ComponentDataModel:
        """Create an empty ComponentDataModel fixture for testing."""
        return ComponentDataModel(None)

    @pytest.fixture
    def realistic_vehicle_data(self) -> ComponentDataModel:
        """Create a realistic vehicle data model based on the JSON file."""
        realistic_data = {
            "Format version": 1,
            "Components": {
                "Flight Controller": {
                    "Product": {
                        "Manufacturer": "Matek",
                        "Model": "H743 SLIM",
                        "URL": "https://www.mateksys.com/?portfolio=h743-slim",
                        "Version": "V3",
                    },
                    "Firmware": {"Type": "ArduCopter", "Version": "4.6.x"},
                    "Specifications": {"MCU Series": "STM32H7xx"},
                    "Notes": "Flight controller with 20x20mm form factor",
                },
                "Frame": {
                    "Product": {
                        "Manufacturer": "Diatone",
                        "Model": "Taycan MX-C",
                        "URL": "https://www.diatone.us/products/diatone-mxc-taycan-duct-3-inch-cinewhoop-fpv-drone",
                        "Version": "2022",
                    },
                    "Specifications": {"TOW min Kg": 0.6, "TOW max Kg": 0.6},
                    "Notes": "A small 3'' ducted frame",
                },
                "RC Controller": {
                    "Product": {
                        "Manufacturer": "Radiomaster",
                        "Model": "TX16S",
                        "URL": "https://www.radiomasterrc.com/products/tx16s-mark-ii-radio-controller",
                        "Version": "MKI",
                    },
                    "Firmware": {"Type": "EdgeTx", "Version": "2.9.2-providence"},
                    "Notes": "Yaapu telem included",
                },
                "RC Receiver": {
                    "Product": {
                        "Manufacturer": "TBS",
                        "Model": "Crossfire RX se",
                        "URL": "https://www.team-blacksheep.com/products/prod:crossfire_nano_se",
                        "Version": "",
                    },
                    "Firmware": {"Type": "Crossfire", "Version": "7"},
                    "FC Connection": {"Type": "SERIAL7", "Protocol": "CRSF"},
                    "Notes": "Connected to flight controller via SERIAL7",
                },
                "Battery": {
                    "Product": {
                        "Manufacturer": "SLS",
                        "Model": "X-Cube 1800mAh 4S1P 14,8V 40C/80C",
                        "URL": "https://www.stefansliposhop.de/akkus/sls-x-cube/",
                        "Version": "",
                    },
                    "Specifications": {
                        "Chemistry": "Lipo",
                        "Volt per cell max": 4.2,
                        "Volt per cell low": 3.6,
                        "Volt per cell crit": 3.55,
                        "Number of cells": 4,
                        "Capacity mAh": 1800,
                    },
                    "Notes": "4S Lipo battery",
                },
                "ESC": {
                    "Product": {
                        "Manufacturer": "Mamba System",
                        "Model": "F45_128k 4in1 ESC",
                        "URL": "https://www.diatone.us/products/mb-f45_128k-bl32-esc",
                        "Version": "1",
                    },
                    "Firmware": {"Type": "BLHeli32", "Version": "32.10"},
                    "FC Connection": {"Type": "Main Out", "Protocol": "DShot600"},
                    "Notes": "4-in-1 ESC with BLHeli32 firmware",
                },
                "Motors": {
                    "Product": {
                        "Manufacturer": "T-Motor",
                        "Model": "T-Motor 15507 3800kv",
                        "URL": "https://www.fpv24.com/de/t-motor/",
                        "Version": "",
                    },
                    "Specifications": {"Poles": 14},
                    "Notes": "High KV motors for 3-inch props",
                },
                "GNSS Receiver": {
                    "Product": {
                        "Manufacturer": "Holybro",
                        "Model": "H-RTK F9P Helical",
                        "URL": "https://holybro.com/products/h-rtk-f9p-gnss-series",
                        "Version": "1",
                    },
                    "Firmware": {"Type": "UBlox", "Version": "1.13.2"},
                    "FC Connection": {"Type": "SERIAL3", "Protocol": "uBlox"},
                    "Notes": "RTK GPS receiver",
                },
            },
            "Program version": "1.4.6",
        }
        return ComponentDataModel(realistic_data)

    def test_init_with_data(self, component_data_model) -> None:
        """Test initialization with data."""
        data = component_data_model.get_component_data()
        assert "Components" in data
        assert "Motor" in data["Components"]
        assert data["Components"]["Motor"]["Type"] == "brushless"
        assert data["Format version"] == 2

    def test_init_empty(self, empty_data_model) -> None:
        """Test initialization with no data."""
        data = empty_data_model.get_component_data()
        assert "Components" in data
        assert data["Components"] == {}
        assert data["Format version"] == 1

    def test_get_component_data(self, component_data_model) -> None:
        """Test getting component data."""
        data = component_data_model.get_component_data()
        assert isinstance(data, dict)
        assert "Components" in data
        assert "Format version" in data

    def test_set_component_value(self, component_data_model) -> None:
        """Test setting a component value."""
        # Set a new value for an existing path
        component_data_model.set_component_value(("Motor", "KV"), 1500)
        assert component_data_model.data["Components"]["Motor"]["KV"] == 1500

        # Set a value for a nested path
        component_data_model.set_component_value(("Motor", "Configuration", "Wiring"), "delta")
        assert component_data_model.data["Components"]["Motor"]["Configuration"]["Wiring"] == "delta"

        # Set a value for a new path
        component_data_model.set_component_value(("Motor", "Weight"), 100)
        assert component_data_model.data["Components"]["Motor"]["Weight"] == 100

        # Test with None value
        component_data_model.set_component_value(("Motor", "Notes"), None)
        assert component_data_model.data["Components"]["Motor"]["Notes"] == ""

    def test_get_component_value(self, component_data_model) -> None:
        """Test getting a component value."""
        # Get an existing value
        value = component_data_model.get_component_value(("Motor", "Type"))
        assert value == "brushless"

        # Get a nested value
        value = component_data_model.get_component_value(("Motor", "Configuration", "Wiring"))
        assert value == "star"

        # Get a non-existent value
        value = component_data_model.get_component_value(("Motor", "NonExistent"))
        assert value == {}

        # Get a non-existent path
        value = component_data_model.get_component_value(("NonExistent", "Path"))
        assert value == {}

    def test_update_from_entries(self, component_data_model) -> None:
        """Test updating from entry widget values."""
        entries = {
            ("Motor", "Type"): "BLDC",
            ("Motor", "KV"): "1200",  # Should be converted to int
            ("Motor", "Configuration", "Wiring"): "Y-connection",
            ("ESC", "Current"): "35.5",  # Should be converted to float
            ("ESC", "Version"): "v2.0",  # Should remain string
        }

        component_data_model._update_from_entries(entries)

        # Check values were updated and converted to appropriate types
        assert component_data_model.data["Components"]["Motor"]["Type"] == "BLDC"
        assert component_data_model.data["Components"]["Motor"]["KV"] == 1200
        assert component_data_model.data["Components"]["Motor"]["Configuration"]["Wiring"] == "Y-connection"
        assert component_data_model.data["Components"]["ESC"]["Current"] == 35.5
        assert component_data_model.data["Components"]["ESC"]["Version"] == "v2.0"

    def test_ensure_format_version(self, component_data_model, empty_data_model) -> None:
        """Test ensuring format version is set."""
        # Should not change existing format version
        original_version = component_data_model.data["Format version"]
        component_data_model.ensure_format_version()
        assert component_data_model.data["Format version"] == original_version

        # Should set format version if missing
        del empty_data_model.data["Format version"]
        empty_data_model.ensure_format_version()
        assert empty_data_model.data["Format version"] == 1

    def test_process_value(self, component_data_model) -> None:
        """Test processing values to the appropriate type."""
        # Test integer conversion
        value = component_data_model._process_value(("Motor", "KV"), "2000")
        assert value == 2000
        assert isinstance(value, int)

        # Test float conversion
        value = component_data_model._process_value(("ESC", "Current"), "25.5")
        assert value == 25.5
        assert isinstance(value, float)

        # Test string handling
        value = component_data_model._process_value(("Motor", "Type"), "  brushless  ")
        assert value == "brushless"
        assert isinstance(value, str)

        # Test handling of non-numeric strings
        value = component_data_model._process_value(("Motor", "Notes"), "Special notes")
        assert value == "Special notes"
        assert isinstance(value, str)

        # Test handling of Version field
        value = component_data_model._process_value(("ESC", "Version"), "1.0")
        assert value == "1.0"  # Should remain a string, not be converted to float
        assert isinstance(value, str)

    def test_set_configuration_template(self, component_data_model) -> None:
        """Test setting the configuration template name."""
        template_name = "Standard Motor Configuration"
        component_data_model.set_configuration_template(template_name)

        assert "Configuration template" in component_data_model.data
        assert component_data_model.data["Configuration template"] == template_name

    def test_get_component(self, component_data_model) -> None:
        """Test getting a specific component's data."""
        # Test getting existing component
        motor_data = component_data_model.get_component("Motor")
        assert isinstance(motor_data, dict)
        assert motor_data["Type"] == "brushless"
        assert motor_data["KV"] == 1000

        # Test getting non-existent component
        nonexistent = component_data_model.get_component("NonExistent")
        assert nonexistent == {}

    def test_update_component(self, component_data_model) -> None:
        """Test updating a component's data."""
        # Update existing component
        new_motor_data = {"Type": "outrunner", "KV": 1500, "Weight": 120}
        component_data_model.update_component("Motor", new_motor_data)

        updated_motor = component_data_model.get_component("Motor")
        assert updated_motor["Type"] == "outrunner"
        assert updated_motor["KV"] == 1500
        assert updated_motor["Weight"] == 120
        assert "Configuration" not in updated_motor  # Confirm it replaces the entire component

        # Add new component
        servo_data = {"Type": "digital", "Torque": 10, "Speed": 0.12}
        component_data_model.update_component("Servo", servo_data)

        assert "Servo" in component_data_model.get_all_components()
        assert component_data_model.get_component("Servo") == servo_data

    def test_extract_component_data_from_entries(self, component_data_model) -> None:
        """Test extracting component data from entries."""
        entries = {
            ("Motor", "Type"): "brushless",
            ("Motor", "KV"): "2200",
            ("Motor", "Configuration", "Wiring"): "delta",
            ("ESC", "Current"): "45",
            ("GPS", "Type"): "ublox",
        }

        # Extract Motor component
        motor_data = component_data_model.extract_component_data_from_entries("Motor", entries)

        assert "Type" in motor_data
        assert motor_data["Type"] == "brushless"
        assert motor_data["KV"] == 2200
        assert "Configuration" in motor_data
        assert motor_data["Configuration"]["Wiring"] == "delta"

        # Verify no other components included
        assert "Current" not in motor_data

        # Extract ESC component
        esc_data = component_data_model.extract_component_data_from_entries("ESC", entries)

        assert "Current" in esc_data
        assert esc_data["Current"] == 45

        # Test non-existent component
        nonexistent = component_data_model.extract_component_data_from_entries("Nonexistent", entries)
        assert nonexistent == {}

    def test_get_all_components(self, component_data_model, empty_data_model) -> None:
        """Test getting all components."""
        # Test with existing components
        components = component_data_model.get_all_components()
        assert len(components) == 2
        assert "Motor" in components
        assert "ESC" in components

        # Test with empty data
        empty_components = empty_data_model.get_all_components()
        assert empty_components == {}

    def test_is_valid_component_data(self, component_data_model, empty_data_model) -> None:
        """Test validating component data structure."""
        # Valid data model
        assert component_data_model.is_valid_component_data() is True

        # Empty but valid data model
        assert empty_data_model.is_valid_component_data() is True

        # Invalid data models
        invalid_model1 = ComponentDataModel({"Missing Components": {}})
        assert invalid_model1.is_valid_component_data() is False

        invalid_model2 = ComponentDataModel({"Components": "Not a dict"})
        assert invalid_model2.is_valid_component_data() is False

        invalid_model3 = ComponentDataModel("Not a dict")
        assert invalid_model3.is_valid_component_data() is False

    def test_none_value_handling(self, component_data_model) -> None:
        """Test handling of None values."""
        # Set None and then ensure it's converted to empty string
        component_data_model.set_component_value(("Motor", "Notes"), None)
        assert component_data_model.get_component_value(("Motor", "Notes")) == ""

        # Update with None in entries dict
        entries = {("Motor", "Description"): None}
        component_data_model._update_from_entries(entries)
        assert component_data_model.get_component_value(("Motor", "Description")) == ""

    def test_component_data_model_integration(self) -> None:
        """Integration test with more complex component structures."""
        # Create a data model with complex nested structure
        complex_data = {
            "Components": {
                "FlightController": {
                    "Brand": "Pixhawk",
                    "Model": "Cube",
                    "IMU": {"Type": "MPU9250", "Count": 3, "Configuration": {"Orientation": "default", "Calibrated": True}},
                    "Ports": {"UART": 6, "I2C": 2, "CAN": 2},
                },
                "Battery": {"Cells": 6, "Capacity": 5000, "C_Rating": 30},
            },
            "Format version": 2,
        }

        model = ComponentDataModel(complex_data)

        # Test deeply nested access
        assert model.get_component_value(("FlightController", "IMU", "Configuration", "Orientation")) == "default"

        # Update deeply nested value
        model.set_component_value(("FlightController", "IMU", "Configuration", "Orientation"), "rotated_90")
        assert model.get_component_value(("FlightController", "IMU", "Configuration", "Orientation")) == "rotated_90"

        # Extract component with complex structure
        entries = {
            ("FlightController", "Brand"): "ArduPilot",
            ("FlightController", "IMU", "Type"): "BMI088",
            ("FlightController", "IMU", "Count"): "2",
            ("FlightController", "IMU", "Configuration", "Orientation"): "rotated_180",
            ("Battery", "Cells"): "8",
        }

        fc_data = model.extract_component_data_from_entries("FlightController", entries)

        assert fc_data["Brand"] == "ArduPilot"
        assert fc_data["IMU"]["Type"] == "BMI088"
        assert fc_data["IMU"]["Count"] == 2  # Converted to int
        assert fc_data["IMU"]["Configuration"]["Orientation"] == "rotated_180"

        # Verify the data model keeps its integrity after multiple operations
        model._update_from_entries(entries)
        all_components = model.get_all_components()

        assert all_components["FlightController"]["Brand"] == "ArduPilot"
        assert all_components["FlightController"]["IMU"]["Configuration"]["Orientation"] == "rotated_180"
        assert all_components["Battery"]["Cells"] == 8

    def test_realistic_vehicle_component_access(self, realistic_vehicle_data) -> None:
        """Test accessing components from realistic vehicle data."""
        # Test flight controller access
        fc_data = realistic_vehicle_data.get_component("Flight Controller")
        assert fc_data["Product"]["Manufacturer"] == "Matek"
        assert fc_data["Product"]["Model"] == "H743 SLIM"
        assert fc_data["Firmware"]["Type"] == "ArduCopter"
        assert fc_data["Specifications"]["MCU Series"] == "STM32H7xx"

        # Test frame specifications
        frame_tow_min = realistic_vehicle_data.get_component_value(("Frame", "Specifications", "TOW min Kg"))
        frame_tow_max = realistic_vehicle_data.get_component_value(("Frame", "Specifications", "TOW max Kg"))
        assert frame_tow_min == 0.6
        assert frame_tow_max == 0.6

        # Test battery specifications
        battery_specs = realistic_vehicle_data.get_component("Battery")["Specifications"]
        assert battery_specs["Chemistry"] == "Lipo"
        assert battery_specs["Number of cells"] == 4
        assert battery_specs["Capacity mAh"] == 1800
        assert battery_specs["Volt per cell max"] == 4.2

        # Test motor specifications
        motor_poles = realistic_vehicle_data.get_component_value(("Motors", "Specifications", "Poles"))
        assert motor_poles == 14

    def test_component_validation_rules(self, realistic_vehicle_data) -> None:
        """Test validation rules with realistic component data."""
        # Test valid TOW values
        is_valid, error = realistic_vehicle_data.validate_entry_limits("0.6", ("Frame", "Specifications", "TOW min Kg"))
        assert is_valid
        assert error == ""

        # Test invalid TOW values
        is_valid, error = realistic_vehicle_data.validate_entry_limits("1000", ("Frame", "Specifications", "TOW max Kg"))
        assert not is_valid
        assert "Takeoff Weight" in error

        # Test valid battery cell count
        is_valid, error = realistic_vehicle_data.validate_entry_limits("4", ("Battery", "Specifications", "Number of cells"))
        assert is_valid

        # Test invalid battery cell count
        is_valid, error = realistic_vehicle_data.validate_entry_limits("100", ("Battery", "Specifications", "Number of cells"))
        assert not is_valid
        assert "Nr of cells" in error

        # Test valid motor poles
        is_valid, error = realistic_vehicle_data.validate_entry_limits("14", ("Motors", "Specifications", "Poles"))
        assert is_valid

        # Test invalid motor poles
        is_valid, error = realistic_vehicle_data.validate_entry_limits("2", ("Motors", "Specifications", "Poles"))
        assert not is_valid
        assert "Motor Poles" in error

    def test_battery_cell_voltage_validation(self, realistic_vehicle_data) -> None:
        """Test battery cell voltage validation."""
        # Test valid Lipo voltages
        is_valid, error, corrected = realistic_vehicle_data.validate_cell_voltage(
            "4.2", ("Battery", "Specifications", "Volt per cell max"), "Lipo"
        )
        assert is_valid
        assert error == ""

        # Test voltage too high for Lipo
        is_valid, error, corrected = realistic_vehicle_data.validate_cell_voltage(
            "5.0", ("Battery", "Specifications", "Volt per cell max"), "Lipo"
        )
        assert not is_valid
        assert "above the Lipo maximum" in error
        assert float(corrected) <= 4.35

        # Test voltage too low for Lipo
        is_valid, error, corrected = realistic_vehicle_data.validate_cell_voltage(
            "2.0", ("Battery", "Specifications", "Volt per cell low"), "Lipo"
        )
        assert not is_valid
        assert "below the Lipo minimum" in error
        assert float(corrected) >= 2.5

        # Test invalid voltage string
        is_valid, error, corrected = realistic_vehicle_data.validate_cell_voltage(
            "invalid", ("Battery", "Specifications", "Volt per cell max"), "Lipo"
        )
        assert not is_valid
        assert "Invalid value" in error
        assert float(corrected) > 0

    def test_fc_manufacturer_and_model_validation(self, realistic_vehicle_data) -> None:
        """Test flight controller manufacturer and model validation."""
        # Test valid manufacturer
        assert realistic_vehicle_data.is_fc_manufacturer_valid("Matek")
        assert realistic_vehicle_data.is_fc_manufacturer_valid("Pixhawk")

        # Test invalid manufacturers
        assert not realistic_vehicle_data.is_fc_manufacturer_valid("Unknown")
        assert not realistic_vehicle_data.is_fc_manufacturer_valid("ArduPilot")
        assert not realistic_vehicle_data.is_fc_manufacturer_valid("")

        # Test valid model
        assert realistic_vehicle_data.is_fc_model_valid("H743 SLIM")
        assert realistic_vehicle_data.is_fc_model_valid("Cube Orange")

        # Test invalid models
        assert not realistic_vehicle_data.is_fc_model_valid("Unknown")
        assert not realistic_vehicle_data.is_fc_model_valid("MAVLink")
        assert not realistic_vehicle_data.is_fc_model_valid("")

    def test_comprehensive_data_validation(self, realistic_vehicle_data) -> None:
        """Test comprehensive data validation with realistic values."""
        doc_dict = {
            "RC_PROTOCOLS": {"Bitmask": {"0": "All", "9": "CRSF", "11": "FPORT"}},
            "BATT_MONITOR": {"values": {"0": "Disabled", "4": "Analog Voltage and Current"}},
            "MOT_PWM_TYPE": {"values": {"0": "Normal", "6": "DShot600"}},
            "GPS_TYPE": {"values": {"0": "None", "2": "uBlox"}},
        }

        entry_values = {
            ("Flight Controller", "Firmware", "Type"): "ArduCopter",
            ("Frame", "Specifications", "TOW min Kg"): "0.6",
            ("Frame", "Specifications", "TOW max Kg"): "0.6",
            ("Battery", "Specifications", "Chemistry"): "Lipo",
            ("Battery", "Specifications", "Number of cells"): "4",
            ("Battery", "Specifications", "Capacity mAh"): "1800",
            ("Battery", "Specifications", "Volt per cell max"): "4.2",
            ("Battery", "Specifications", "Volt per cell low"): "3.6",
            ("Battery", "Specifications", "Volt per cell crit"): "3.55",
            ("Motors", "Specifications", "Poles"): "14",
            ("RC Receiver", "FC Connection", "Type"): "SERIAL7",
            ("RC Receiver", "FC Connection", "Protocol"): "CRSF",
            ("ESC", "FC Connection", "Type"): "Main Out",
            ("ESC", "FC Connection", "Protocol"): "DShot600",
            ("GNSS Receiver", "FC Connection", "Type"): "SERIAL3",
            ("GNSS Receiver", "FC Connection", "Protocol"): "uBlox",
        }

        is_valid, errors = realistic_vehicle_data.validate_all_data(entry_values, doc_dict)
        assert is_valid
        assert len(errors) == 0

    def test_duplicate_connection_validation(self, realistic_vehicle_data) -> None:
        """Test validation of duplicate FC connections."""
        doc_dict = {
            "RC_PROTOCOLS": {"Bitmask": {"9": "CRSF"}},
            "BATT_MONITOR": {"values": {"4": "Analog Voltage and Current"}},
            "MOT_PWM_TYPE": {"values": {"6": "DShot600"}},
            "GPS_TYPE": {"values": {"2": "uBlox"}},
        }

        # Test duplicate serial connections (should fail)
        entry_values = {
            ("RC Receiver", "FC Connection", "Type"): "SERIAL3",
            ("GNSS Receiver", "FC Connection", "Type"): "SERIAL3",
            ("RC Receiver", "FC Connection", "Protocol"): "CRSF",
            ("GNSS Receiver", "FC Connection", "Protocol"): "uBlox",
        }

        is_valid, errors = realistic_vehicle_data.validate_all_data(entry_values, doc_dict)
        assert not is_valid
        assert any("Duplicate FC connection" in error for error in errors)

        # Test allowed CAN connections (should pass)
        entry_values_can = {
            ("RC Receiver", "FC Connection", "Type"): "CAN1",
            ("GNSS Receiver", "FC Connection", "Type"): "CAN1",
            ("RC Receiver", "FC Connection", "Protocol"): "CRSF",
            ("GNSS Receiver", "FC Connection", "Protocol"): "uBlox",
        }

        is_valid, errors = realistic_vehicle_data.validate_all_data(entry_values_can, doc_dict)
        assert is_valid

    def test_fc_parameter_processing_gnss(self, realistic_vehicle_data) -> None:
        """Test GNSS parameter processing."""
        fc_parameters = {
            "GPS_TYPE": 2,  # uBlox
            "SERIAL3_PROTOCOL": 5,  # GPS
        }
        doc_dict = {"GPS_TYPE": {"values": {"2": "uBlox"}}}

        realistic_vehicle_data.process_fc_parameters(fc_parameters, doc_dict)

        gnss_type = realistic_vehicle_data.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        gnss_protocol = realistic_vehicle_data.get_component_value(("GNSS Receiver", "FC Connection", "Protocol"))

        assert gnss_type == "SERIAL3"
        assert gnss_protocol == "uBlox"

    def test_fc_parameter_processing_rc(self, realistic_vehicle_data) -> None:
        """Test RC parameter processing."""
        fc_parameters = {
            "RC_PROTOCOLS": 512,  # 2^9 = CRSF protocol
            "SERIAL7_PROTOCOL": 23,  # RCIN
        }
        doc_dict = {"RC_PROTOCOLS": {"Bitmask": {"9": "CRSF"}}}

        realistic_vehicle_data.process_fc_parameters(fc_parameters, doc_dict)

        rc_type = realistic_vehicle_data.get_component_value(("RC Receiver", "FC Connection", "Type"))
        rc_protocol = realistic_vehicle_data.get_component_value(("RC Receiver", "FC Connection", "Protocol"))

        assert rc_type == "SERIAL7"
        assert rc_protocol == "CRSF"

    def test_fc_parameter_processing_esc_dshot(self, realistic_vehicle_data) -> None:
        """Test ESC parameter processing for DShot."""
        fc_parameters = {
            "MOT_PWM_TYPE": 6,  # DShot600
            "SERVO1_FUNCTION": 33,  # Motor1
            "SERVO2_FUNCTION": 34,  # Motor2
            "SERVO3_FUNCTION": 35,  # Motor3
            "SERVO4_FUNCTION": 36,  # Motor4
            "SERVO_BLH_POLES": 14,
        }
        doc_dict = {"MOT_PWM_TYPE": {"values": {"6": "DShot600"}}}

        realistic_vehicle_data.process_fc_parameters(fc_parameters, doc_dict)

        esc_type = realistic_vehicle_data.get_component_value(("ESC", "FC Connection", "Type"))
        esc_protocol = realistic_vehicle_data.get_component_value(("ESC", "FC Connection", "Protocol"))
        motor_poles = realistic_vehicle_data.get_component_value(("Motors", "Specifications", "Poles"))

        assert esc_type == "Main Out"
        assert esc_protocol == "DShot600"
        assert motor_poles == 14

    def test_fc_parameter_processing_battery_monitor(self, realistic_vehicle_data) -> None:
        """Test battery monitor parameter processing."""
        fc_parameters = {
            "BATT_MONITOR": 4,  # Analog Voltage and Current
        }
        doc_dict = {"BATT_MONITOR": {"values": {"4": "Analog Voltage and Current"}}}

        realistic_vehicle_data.process_fc_parameters(fc_parameters, doc_dict)

        batt_type = realistic_vehicle_data.get_component_value(("Battery Monitor", "FC Connection", "Type"))
        batt_protocol = realistic_vehicle_data.get_component_value(("Battery Monitor", "FC Connection", "Protocol"))

        assert batt_type == "Analog"
        assert batt_protocol == "Analog Voltage and Current"

    def test_fc_parameter_processing_telemetry(self, realistic_vehicle_data) -> None:
        """Test telemetry parameter processing."""
        fc_parameters = {
            "SERIAL1_PROTOCOL": 2,  # MAVLink2
        }
        doc_dict = {}

        realistic_vehicle_data.process_fc_parameters(fc_parameters, doc_dict)

        telem_type = realistic_vehicle_data.get_component_value(("Telemetry", "FC Connection", "Type"))
        telem_protocol = realistic_vehicle_data.get_component_value(("Telemetry", "FC Connection", "Protocol"))

        assert telem_type == "SERIAL1"
        assert telem_protocol == "MAVLink2"

    def test_update_json_structure(self, empty_data_model) -> None:
        """Test updating JSON structure for old files."""
        # Start with minimal data
        empty_data_model.data = {"Components": {}}

        empty_data_model.update_json_structure()

        # Check that all required fields are added
        assert "Battery" in empty_data_model.data["Components"]
        assert "Specifications" in empty_data_model.data["Components"]["Battery"]
        assert "Chemistry" in empty_data_model.data["Components"]["Battery"]["Specifications"]
        assert empty_data_model.data["Components"]["Battery"]["Specifications"]["Chemistry"] == "Lipo"

        assert "Frame" in empty_data_model.data["Components"]
        assert "Specifications" in empty_data_model.data["Components"]["Frame"]
        assert "TOW min Kg" in empty_data_model.data["Components"]["Frame"]["Specifications"]
        assert "TOW max Kg" in empty_data_model.data["Components"]["Frame"]["Specifications"]

        assert "Flight Controller" in empty_data_model.data["Components"]
        assert "Specifications" in empty_data_model.data["Components"]["Flight Controller"]
        assert "MCU Series" in empty_data_model.data["Components"]["Flight Controller"]["Specifications"]

        assert "Program version" in empty_data_model.data

    def test_rename_old_gnss_receiver_key(self, component_data_model) -> None:
        """Test renaming old 'GNSS receiver' to 'GNSS Receiver'."""
        # Add old key format
        component_data_model.data["Components"]["GNSS receiver"] = {
            "Product": {"Manufacturer": "Holybro", "Model": "H-RTK F9P"}
        }

        component_data_model.update_json_structure()

        # Check that old key is removed and new key exists
        assert "GNSS receiver" not in component_data_model.data["Components"]
        assert "GNSS Receiver" in component_data_model.data["Components"]
        assert component_data_model.data["Components"]["GNSS Receiver"]["Product"]["Manufacturer"] == "Holybro"

    def test_esc_protocol_values_by_connection_type(self, realistic_vehicle_data) -> None:
        """Test getting ESC protocol values based on connection type."""
        doc_dict = {"MOT_PWM_TYPE": {"values": {"0": "Normal", "6": "DShot600"}}}

        # Test CAN connection
        can_protocols = realistic_vehicle_data.get_esc_protocol_values("CAN1", doc_dict)
        assert "DroneCAN" in can_protocols

        # Test serial connection
        serial_protocols = realistic_vehicle_data.get_esc_protocol_values("SERIAL5", doc_dict)
        assert "FETtecOneWire" in serial_protocols

        # Test main out connection
        main_out_protocols = realistic_vehicle_data.get_esc_protocol_values("Main Out", doc_dict)
        assert "Normal" in main_out_protocols
        assert "DShot600" in main_out_protocols

    def test_complex_component_extraction(self, realistic_vehicle_data) -> None:
        """Test extracting complex component data."""
        entries = {
            ("Flight Controller", "Product", "Manufacturer"): "Matek",
            ("Flight Controller", "Product", "Model"): "H743 SLIM",
            ("Flight Controller", "Product", "Version"): "V3",
            ("Flight Controller", "Firmware", "Type"): "ArduCopter",
            ("Flight Controller", "Firmware", "Version"): "4.6.x",
            ("Flight Controller", "Specifications", "MCU Series"): "STM32H7xx",
            ("Flight Controller", "Notes"): "Updated flight controller",
            ("Battery", "Specifications", "Number of cells"): "6",
            ("Motors", "Specifications", "Poles"): "12",
        }

        # Extract Flight Controller component
        fc_data = realistic_vehicle_data.extract_component_data_from_entries("Flight Controller", entries)

        assert fc_data["Product"]["Manufacturer"] == "Matek"
        assert fc_data["Product"]["Model"] == "H743 SLIM"
        assert fc_data["Product"]["Version"] == "V3"  # Should remain string
        assert fc_data["Firmware"]["Type"] == "ArduCopter"
        assert fc_data["Firmware"]["Version"] == "4.6.x"  # Should remain string
        assert fc_data["Specifications"]["MCU Series"] == "STM32H7xx"
        assert fc_data["Notes"] == "Updated flight controller"

        # Verify no other component data is included
        assert "Number of cells" not in str(fc_data)
        assert "Poles" not in str(fc_data)

    def test_derive_initial_template_name(self, realistic_vehicle_data) -> None:
        """Test deriving initial template name from component data."""
        # Test with complete product data
        component_data = {"Product": {"Manufacturer": "Matek", "Model": "H743 SLIM"}}
        template_name = realistic_vehicle_data.derive_initial_template_name(component_data)
        assert template_name == "Matek H743 SLIM"

        # Test with partial product data
        component_data_partial = {"Product": {"Manufacturer": "Holybro"}}
        template_name = realistic_vehicle_data.derive_initial_template_name(component_data_partial)
        assert template_name == "Holybro "

        # Test with no product data
        component_data_empty = {}
        template_name = realistic_vehicle_data.derive_initial_template_name(component_data_empty)
        assert template_name == ""

    def test_voltage_relationship_validation(self, realistic_vehicle_data) -> None:
        """Test validation of battery voltage relationships."""
        doc_dict = {}

        # Test valid voltage relationships
        valid_entries = {
            ("Battery", "Specifications", "Chemistry"): "Lipo",
            ("Battery", "Specifications", "Volt per cell max"): "4.2",
            ("Battery", "Specifications", "Volt per cell low"): "3.6",
            ("Battery", "Specifications", "Volt per cell crit"): "3.55",
        }

        is_valid, errors = realistic_vehicle_data.validate_all_data(valid_entries, doc_dict)
        assert is_valid
        assert len(errors) == 0

        # Test invalid voltage relationships - low >= max
        invalid_entries = {
            ("Battery", "Specifications", "Chemistry"): "Lipo",
            ("Battery", "Specifications", "Volt per cell max"): "3.6",
            ("Battery", "Specifications", "Volt per cell low"): "3.6",
            ("Battery", "Specifications", "Volt per cell crit"): "3.55",
        }

        is_valid, errors = realistic_vehicle_data.validate_all_data(invalid_entries, doc_dict)
        assert not is_valid
        assert any("Battery Cell Low voltage must be lower than max voltage" in error for error in errors)

        # Test invalid voltage relationships - crit >= low
        invalid_entries2 = {
            ("Battery", "Specifications", "Chemistry"): "Lipo",
            ("Battery", "Specifications", "Volt per cell max"): "4.2",
            ("Battery", "Specifications", "Volt per cell low"): "3.55",
            ("Battery", "Specifications", "Volt per cell crit"): "3.55",
        }

        is_valid, errors = realistic_vehicle_data.validate_all_data(invalid_entries2, doc_dict)
        assert not is_valid
        assert any("Battery Cell Crit voltage must be lower than low voltage" in error for error in errors)

    def test_error_handling_invalid_parameters(self, realistic_vehicle_data) -> None:
        """Test error handling for invalid parameter values."""
        # Test invalid GPS_TYPE
        fc_parameters = {
            "GPS_TYPE": "invalid_string",
        }
        doc_dict = {}

        # Should not raise exception, should log error and set to default
        realistic_vehicle_data.process_fc_parameters(fc_parameters, doc_dict)
        gnss_type = realistic_vehicle_data.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        assert gnss_type == "None"

        # Test invalid MOT_PWM_TYPE
        fc_parameters_invalid = {
            "MOT_PWM_TYPE": "not_a_number",
        }

        realistic_vehicle_data.process_fc_parameters(fc_parameters_invalid, doc_dict)
        # Should handle gracefully without crashing

        # Test invalid BATT_MONITOR
        fc_parameters_invalid_batt = {
            "BATT_MONITOR": 999,  # Non-existent value
        }

        realistic_vehicle_data.process_fc_parameters(fc_parameters_invalid_batt, doc_dict)
        # Should handle gracefully without crashing

    def test_has_components_check(self, realistic_vehicle_data, empty_data_model) -> None:
        """Test checking if data model has components."""
        # Realistic data should have components
        assert realistic_vehicle_data.has_components()

        # Empty data should not have components
        assert not empty_data_model.has_components()

        # Add a component to empty model
        empty_data_model.update_component("Test Component", {"Type": "Test"})
        assert empty_data_model.has_components()

    def test_multiple_serial_devices_same_type(self, realistic_vehicle_data) -> None:
        """Test handling multiple serial devices of the same type."""
        fc_parameters = {
            "SERIAL1_PROTOCOL": 2,  # MAVLink2 - first telemetry
            "SERIAL2_PROTOCOL": 2,  # MAVLink2 - second telemetry (should be ignored)
            "SERIAL3_PROTOCOL": 5,  # GPS - first GNSS
            "SERIAL4_PROTOCOL": 5,  # GPS - second GNSS (should be ignored)
        }
        doc_dict = {}

        realistic_vehicle_data.process_fc_parameters(fc_parameters, doc_dict)

        # Should only set first occurrence of each type
        telem_type = realistic_vehicle_data.get_component_value(("Telemetry", "FC Connection", "Type"))
        gnss_type = realistic_vehicle_data.get_component_value(("GNSS Receiver", "FC Connection", "Type"))

        assert telem_type == "SERIAL1"
        assert gnss_type == "SERIAL3"

    def test_can_gnss_connection(self, realistic_vehicle_data) -> None:
        """Test CAN GNSS connection processing."""
        fc_parameters = {
            "GPS_TYPE": 9,  # DroneCAN
            "CAN_D1_PROTOCOL": 1,  # DroneCAN protocol
            "CAN_P1_DRIVER": 1,  # CAN1 driver
        }
        doc_dict = {"GPS_TYPE": {"values": {"9": "DroneCAN"}}}

        realistic_vehicle_data.process_fc_parameters(fc_parameters, doc_dict)

        gnss_type = realistic_vehicle_data.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        gnss_protocol = realistic_vehicle_data.get_component_value(("GNSS Receiver", "FC Connection", "Protocol"))

        assert gnss_type == "CAN1"
        assert gnss_protocol == "DroneCAN"

    def test_motor_poles_from_fettec_parameters(self, realistic_vehicle_data) -> None:
        """Test motor poles detection from FETtec parameters."""
        fc_parameters = {
            "MOT_PWM_TYPE": 0,  # Normal (not DShot)
            "SERVO_FTW_MASK": 15,  # FETtec motors on channels 1-4
            "SERVO_FTW_POLES": 12,  # 12 pole motors
        }
        doc_dict = {}

        realistic_vehicle_data.process_fc_parameters(fc_parameters, doc_dict)

        motor_poles = realistic_vehicle_data.get_component_value(("Motors", "Specifications", "Poles"))
        assert motor_poles == 12

    def test_edge_cases_process_value(self, component_data_model) -> None:
        """Test edge cases in _process_value method."""
        # Test non-Version field with numeric string
        path = ("Test", "Numeric")

        # Test int conversion
        result = component_data_model._process_value(path, "42")
        assert result == 42
        assert isinstance(result, int)

        # Test float conversion when int fails
        result = component_data_model._process_value(path, "42.5")
        assert result == 42.5
        assert isinstance(result, float)

        # Test string fallback when both fail
        result = component_data_model._process_value(path, "not_a_number")
        assert result == "not_a_number"
        assert isinstance(result, str)

        # Test Version field always returns string
        version_path = ("Test", "Version")
        result = component_data_model._process_value(version_path, "42")
        assert result == "42"
        assert isinstance(result, str)

    def test_get_component_value_edge_cases(self, component_data_model) -> None:
        """Test edge cases in get_component_value method."""
        # Test accessing non-existent nested path
        result = component_data_model.get_component_value(("NonExistent", "Path", "Deep"))
        assert result == {}

        # Test with unusual data types in the structure
        component_data_model.data["Components"]["Test"] = {
            "unusual_type": ["list", "data"],
            "tuple_data": (1, 2, 3),
            "none_value": None,
        }

        # Test list conversion to string
        result = component_data_model.get_component_value(("Test", "unusual_type"))
        assert result == "['list', 'data']"

        # Test tuple conversion to string
        result = component_data_model.get_component_value(("Test", "tuple_data"))
        assert result == "(1, 2, 3)"

    def test_update_component_without_components_key(self, empty_data_model) -> None:
        """Test updating component when Components key doesn't exist."""
        # Remove Components key if it exists
        if "Components" in empty_data_model.data:
            del empty_data_model.data["Components"]

        # Update component should create Components key
        test_data = {"Type": "Test", "Value": 42}
        empty_data_model.update_component("TestComponent", test_data)

        assert "Components" in empty_data_model.data
        assert empty_data_model.data["Components"]["TestComponent"] == test_data

    def test_derive_initial_template_name_edge_cases(self, realistic_vehicle_data) -> None:
        """Test edge cases in derive_initial_template_name."""
        # Test with missing Model
        component_data = {"Product": {"Manufacturer": "Matek"}}
        result = realistic_vehicle_data.derive_initial_template_name(component_data)
        assert result == "Matek "

        # Test with missing Manufacturer
        component_data = {"Product": {"Model": "H743 SLIM"}}
        result = realistic_vehicle_data.derive_initial_template_name(component_data)
        assert result == " H743 SLIM"

        # Test with empty Product dict
        component_data = {"Product": {}}
        result = realistic_vehicle_data.derive_initial_template_name(component_data)
        assert result == ""  # Empty product data returns empty string

        # Test with missing Product key
        component_data = {"Other": "data"}
        result = realistic_vehicle_data.derive_initial_template_name(component_data)
        assert result == ""

    def test_validation_rules_edge_cases(self, realistic_vehicle_data) -> None:
        """Test validation rules with edge cases."""
        # Test path not in validation rules
        is_valid, error = realistic_vehicle_data.validate_entry_limits("42", ("Unknown", "Path"))
        assert is_valid
        assert error == ""

        # Test validation with boundary values
        is_valid, error = realistic_vehicle_data.validate_entry_limits("0.01", ("Frame", "Specifications", "TOW min Kg"))
        assert is_valid

        is_valid, error = realistic_vehicle_data.validate_entry_limits("600", ("Frame", "Specifications", "TOW max Kg"))
        assert is_valid

        # Test validation with values outside limits
        is_valid, error = realistic_vehicle_data.validate_entry_limits("0.005", ("Frame", "Specifications", "TOW min Kg"))
        assert not is_valid
        assert "Takeoff Weight" in error

        # Test validation with invalid value type
        is_valid, error = realistic_vehicle_data.validate_entry_limits(
            "not_a_number", ("Frame", "Specifications", "TOW min Kg")
        )
        assert not is_valid

    def test_battery_cell_voltage_validation_edge_cases(self, realistic_vehicle_data) -> None:
        """Test battery cell voltage validation edge cases."""
        # Test with different chemistry types
        chemistries = ["LiFe", "Li-ion", "NiMH"]

        for chemistry in chemistries:
            # Test with valid voltage for each chemistry
            is_valid, error, corrected = realistic_vehicle_data.validate_cell_voltage(
                "3.6", ("Battery", "Specifications", "Volt per cell low"), chemistry
            )
            # Should be valid for most chemistries or provide appropriate feedback
            assert isinstance(is_valid, bool)
            assert isinstance(error, str)
            assert isinstance(corrected, str)

        # Test with extremely high voltage
        is_valid, error, corrected = realistic_vehicle_data.validate_cell_voltage(
            "10.0", ("Battery", "Specifications", "Volt per cell max"), "Lipo"
        )
        assert not is_valid
        assert "above" in error.lower()

        # Test with negative voltage
        is_valid, error, corrected = realistic_vehicle_data.validate_cell_voltage(
            "-1.0", ("Battery", "Specifications", "Volt per cell low"), "Lipo"
        )
        assert not is_valid
        assert "below" in error.lower()

        # Test with different voltage field types
        for field in ["Volt per cell max", "Volt per cell low", "Volt per cell crit"]:
            is_valid, error, corrected = realistic_vehicle_data.validate_cell_voltage(
                "invalid_voltage", (("Battery", "Specifications", field)), "Lipo"
            )
            assert not is_valid
            assert "Invalid value" in error
            assert float(corrected) > 0

    def test_fc_parameter_processing_error_handling(self, realistic_vehicle_data) -> None:
        """Test error handling in FC parameter processing."""
        # Test with empty dictionaries
        realistic_vehicle_data.process_fc_parameters({}, {})

        # Test with invalid parameter types
        fc_parameters = {
            "GPS_TYPE": [1, 2, 3],  # List instead of int
            "MOT_PWM_TYPE": {"invalid": "dict"},  # Dict instead of int
            "BATT_MONITOR": "string_value",  # String that can't convert to int
            "RC_PROTOCOLS": "not_a_number",
        }

        # Should handle errors gracefully without crashing
        realistic_vehicle_data.process_fc_parameters(fc_parameters, {})

        # Test with very large numbers
        fc_parameters_large = {"GPS_TYPE": 999999, "MOT_PWM_TYPE": 999999, "BATT_MONITOR": 999999}

        realistic_vehicle_data.process_fc_parameters(fc_parameters_large, {})

    def test_dict_verification_methods(self, realistic_vehicle_data) -> None:
        """Test dictionary verification methods."""
        # Test _verify_dict_is_uptodate with missing doc
        result = realistic_vehicle_data._verify_dict_is_uptodate({}, {}, "missing_key", "values")
        assert not result

        # Test with missing doc_key
        doc = {"other_key": {"values": {}}}
        result = realistic_vehicle_data._verify_dict_is_uptodate(doc, {}, "missing_key", "values")
        assert not result

        # Test with missing doc_dict
        doc = {"test_key": {"other_dict": {}}}
        result = realistic_vehicle_data._verify_dict_is_uptodate(doc, {}, "test_key", "values")
        assert not result

        # Test with mismatched protocols
        doc = {"test_key": {"values": {"1": "Protocol1", "2": "Protocol2"}}}
        dict_to_check = {"1": {"protocol": "DifferentProtocol"}, "2": {"protocol": "Protocol2"}}
        result = realistic_vehicle_data._verify_dict_is_uptodate(doc, dict_to_check, "test_key", "values")
        assert not result

        # Test with missing protocol in dict_to_check
        doc = {"test_key": {"values": {"1": "Protocol1", "3": "Protocol3"}}}
        dict_to_check = {"1": {"protocol": "Protocol1"}}
        result = realistic_vehicle_data._verify_dict_is_uptodate(doc, dict_to_check, "test_key", "values")
        assert not result

    def test_reverse_key_search_method(self, realistic_vehicle_data) -> None:
        """Test _reverse_key_search static method."""
        # Test with matching values
        doc = {"TEST_PARAM": {"values": {"1": 10.0, "2": 20.0, "3": 30.0}}}

        result = realistic_vehicle_data._reverse_key_search(doc, "TEST_PARAM", [10.0, 20.0], [1, 2])
        assert result == [1, 2]

        # Test with no matching values (should return fallbacks)
        result = realistic_vehicle_data._reverse_key_search(doc, "TEST_PARAM", [99.0], [99])
        assert result == [99]

        # Test with mismatched lengths (should log error and return found matches, not fallbacks)
        result = realistic_vehicle_data._reverse_key_search(doc, "TEST_PARAM", [10.0, 20.0], [1])
        assert result == [1, 2]  # Returns found matches even with length mismatch

    def test_serial_parameter_processing_edge_cases(self, realistic_vehicle_data) -> None:
        """Test edge cases in serial parameter processing."""
        # Test RC_PROTOCOLS with non-power-of-two value (multiple protocols)
        fc_parameters = {
            "RC_PROTOCOLS": 1536,  # 512 + 1024 = 2^9 + 2^10 (multiple bits set)
        }

        realistic_vehicle_data.process_fc_parameters(fc_parameters, {})
        # Should not set RC protocol when multiple bits are set

        # Test with missing SERIAL*_PROTOCOL parameters
        fc_parameters = {
            "SERIAL1_PROTOCOL": None,  # Should be skipped
        }

        realistic_vehicle_data.process_fc_parameters(fc_parameters, {})

        # Test with invalid serial protocol numbers
        fc_parameters = {
            "SERIAL1_PROTOCOL": "invalid",
            "SERIAL2_PROTOCOL": 999999,  # Non-existent protocol
        }

        realistic_vehicle_data.process_fc_parameters(fc_parameters, {})

    def test_esc_protocol_values_edge_cases(self, realistic_vehicle_data) -> None:
        """Test edge cases in get_esc_protocol_values."""
        # Test with short connection type strings
        result = realistic_vehicle_data.get_esc_protocol_values("CA", {})
        assert result == []

        result = realistic_vehicle_data.get_esc_protocol_values("SER", {})
        assert result == []

        # Test with empty doc_dict
        result = realistic_vehicle_data.get_esc_protocol_values("Main Out", {})
        assert result == []

        # Test with Q_M_PWM_TYPE in doc_dict
        doc_dict = {"Q_M_PWM_TYPE": {"values": {"0": "QuadPlane Normal", "6": "QuadPlane DShot600"}}}
        result = realistic_vehicle_data.get_esc_protocol_values("Main Out", doc_dict)
        assert "QuadPlane Normal" in result
        assert "QuadPlane DShot600" in result

    def test_combobox_values_edge_cases(self, realistic_vehicle_data) -> None:
        """Test edge cases in get_combobox_values_for_path."""
        # Test with path not in combobox_dict
        unknown_path = ("Unknown", "Component", "Property")
        result = realistic_vehicle_data.get_combobox_values_for_path(unknown_path, {})
        assert result == ()

        # Test with empty doc_dict for known paths
        doc_dict = {}
        result = realistic_vehicle_data.get_combobox_values_for_path(("RC Receiver", "FC Connection", "Protocol"), doc_dict)
        # Should fall back to hardcoded values
        assert len(result) > 0

        # Test with Bitmask instead of values in doc_dict
        doc_dict = {"RC_PROTOCOLS": {"Bitmask": {"0": "All", "9": "CRSF"}}}
        result = realistic_vehicle_data.get_combobox_values_for_path(("RC Receiver", "FC Connection", "Protocol"), doc_dict)
        assert "All" in result
        assert "CRSF" in result

        # Test with empty values in doc_dict
        doc_dict = {"RC_PROTOCOLS": {"values": {}}}
        result = realistic_vehicle_data.get_combobox_values_for_path(("RC Receiver", "FC Connection", "Protocol"), doc_dict)
        # Should fall back to hardcoded values
        assert len(result) > 0

    def test_comprehensive_validation_edge_cases(self, realistic_vehicle_data) -> None:
        """Test comprehensive validation with edge cases."""
        doc_dict = {
            "RC_PROTOCOLS": {"Bitmask": {"9": "CRSF"}},
            "BATT_MONITOR": {"values": {"4": "Analog Voltage and Current"}},
            "MOT_PWM_TYPE": {"values": {"6": "DShot600"}},
            "GPS_TYPE": {"values": {"2": "uBlox"}},
        }

        # Test invalid combobox value
        entry_values = {
            ("RC Receiver", "FC Connection", "Protocol"): "InvalidProtocol",
        }

        is_valid, errors = realistic_vehicle_data.validate_all_data(entry_values, doc_dict)
        assert not is_valid
        assert any("Invalid value" in error for error in errors)

        # Test special duplicate connection cases
        entry_values = {
            ("Telemetry", "FC Connection", "Type"): "SERIAL1",
            ("RC Receiver", "FC Connection", "Type"): "SERIAL1",  # Should be allowed
        }

        is_valid, errors = realistic_vehicle_data.validate_all_data(entry_values, doc_dict)
        assert is_valid  # Telemetry and RC Receiver can share connections

        # Test ESC and Battery Monitor sharing connection with ESC protocol
        realistic_vehicle_data.set_component_value(("Battery Monitor", "FC Connection", "Protocol"), "ESC")
        entry_values = {
            ("Battery Monitor", "FC Connection", "Type"): "SERIAL2",
            ("ESC", "FC Connection", "Type"): "SERIAL2",  # Should be allowed with ESC protocol
        }

        is_valid, errors = realistic_vehicle_data.validate_all_data(entry_values, doc_dict)
        assert is_valid

        # Test voltage validation with ValueError in float conversion
        entry_values = {
            ("Battery", "Specifications", "Volt per cell max"): "4.2",
            ("Battery", "Specifications", "Volt per cell low"): "not_a_number",  # Should trigger ValueError
        }

        is_valid, errors = realistic_vehicle_data.validate_all_data(entry_values, doc_dict)
        # Should handle ValueError gracefully

    def test_can_gnss_connection_edge_cases(self, realistic_vehicle_data) -> None:
        """Test edge cases in CAN GNSS connection processing."""
        # Test CAN2 configuration
        fc_parameters = {
            "GPS_TYPE": 9,  # DroneCAN
            "CAN_D2_PROTOCOL": 1,  # DroneCAN protocol
            "CAN_P2_DRIVER": 2,  # CAN2 driver
        }
        doc_dict = {"GPS_TYPE": {"values": {"9": "DroneCAN"}}}

        realistic_vehicle_data.process_fc_parameters(fc_parameters, doc_dict)

        gnss_type = realistic_vehicle_data.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        assert gnss_type == "CAN2"

        # Test invalid CAN configuration
        fc_parameters = {
            "GPS_TYPE": 9,  # DroneCAN
            "CAN_D1_PROTOCOL": 0,  # Wrong protocol
            "CAN_P1_DRIVER": 2,  # Wrong driver for CAN1
        }

        realistic_vehicle_data.process_fc_parameters(fc_parameters, doc_dict)

        gnss_type = realistic_vehicle_data.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        assert gnss_type == "None"  # Should fall back to None for invalid config

    def test_esc_connection_main_out_vs_aio(self, realistic_vehicle_data) -> None:
        """Test ESC connection detection between Main Out and AIO."""
        # Test AIO configuration (no motors on main out)
        fc_parameters = {
            "MOT_PWM_TYPE": 6,  # DShot600
            "SERVO1_FUNCTION": 0,  # Disabled
            "SERVO2_FUNCTION": 0,  # Disabled
            "SERVO3_FUNCTION": 0,  # Disabled
            "SERVO4_FUNCTION": 0,  # Disabled
            "SERVO5_FUNCTION": 0,  # Disabled
            "SERVO6_FUNCTION": 0,  # Disabled
            "SERVO7_FUNCTION": 0,  # Disabled
            "SERVO8_FUNCTION": 0,  # Disabled
            "SERVO9_FUNCTION": 33,  # Motor1 on AUX
            "SERVO10_FUNCTION": 34,  # Motor2 on AUX
        }
        doc_dict = {"MOT_PWM_TYPE": {"values": {"6": "DShot600"}}}

        realistic_vehicle_data.process_fc_parameters(fc_parameters, doc_dict)

        esc_type = realistic_vehicle_data.get_component_value(("ESC", "FC Connection", "Type"))
        assert esc_type == "AIO"  # Should be AIO when no motors on main out

        # Test with some motors on main out (should be Main Out)
        fc_parameters["SERVO2_FUNCTION"] = 34  # Motor2 on main out

        realistic_vehicle_data.process_fc_parameters(fc_parameters, doc_dict)

        esc_type = realistic_vehicle_data.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        # Should be Main Out when motors are on main out channels

    def test_save_to_filesystem_method(self, realistic_vehicle_data) -> None:
        """Test save_to_filesystem method with mocked filesystem."""
        from unittest.mock import MagicMock, Mock  # pylint: disable=import-outside-toplevel

        # Create a mock filesystem
        mock_filesystem = Mock()
        mock_filesystem.save_vehicle_components_json_data = MagicMock(return_value=(True, "Success"))
        mock_filesystem.vehicle_dir = "/mock/path"

        # Create test entry values
        entry_values = {
            ("Flight Controller", "Product", "Manufacturer"): "TestManufacturer",
            ("Battery", "Specifications", "Capacity mAh"): "2000",
        }

        # Call save_to_filesystem
        success, message = realistic_vehicle_data.save_to_filesystem(mock_filesystem, entry_values)

        # Verify the method was called correctly
        assert success is True
        assert message == "Success"
        mock_filesystem.save_vehicle_components_json_data.assert_called_once()

        # Verify that entry values were processed into the model
        assert (
            realistic_vehicle_data.get_component_value(("Flight Controller", "Product", "Manufacturer")) == "TestManufacturer"
        )
        assert realistic_vehicle_data.get_component_value(("Battery", "Specifications", "Capacity mAh")) == 2000

    def test_motor_poles_no_dshot_no_fettec(self, realistic_vehicle_data) -> None:
        """Test motor poles when neither DShot nor FETtec are configured."""
        # Get initial motor poles value
        initial_motor_poles = realistic_vehicle_data.get_component_value(("Motors", "Specifications", "Poles"))

        fc_parameters = {
            "MOT_PWM_TYPE": 0,  # Normal PWM
            "SERVO_FTW_MASK": 0,  # No FETtec
        }
        doc_dict = {}

        realistic_vehicle_data.process_fc_parameters(fc_parameters, doc_dict)

        # Should not change motor poles when neither DShot nor FETtec are configured
        motor_poles = realistic_vehicle_data.get_component_value(("Motors", "Specifications", "Poles"))
        # Motor poles should remain unchanged from initial value
        assert motor_poles == initial_motor_poles

    def test_esc_protocol_fallback_to_dict(self, realistic_vehicle_data) -> None:
        """Test ESC protocol fallback to MOT_PWM_TYPE_DICT when doc is unavailable."""
        fc_parameters = {
            "MOT_PWM_TYPE": 6,  # DShot600
            "SERVO1_FUNCTION": 33,  # Motor1
        }

        # Empty doc_dict to force fallback
        doc_dict = {}

        realistic_vehicle_data.process_fc_parameters(fc_parameters, doc_dict)

        esc_protocol = realistic_vehicle_data.get_component_value(("ESC", "FC Connection", "Protocol"))
        # Should use fallback dictionary
        assert esc_protocol != ""

    def test_battery_monitor_error_handling(self, realistic_vehicle_data) -> None:
        """Test battery monitor parameter processing with error conditions."""
        # Test with invalid BATT_MONITOR value that can't be converted to int
        fc_parameters = {
            "BATT_MONITOR": {"invalid": "dict_type"},
        }

        # Should handle the error gracefully without crashing
        realistic_vehicle_data.process_fc_parameters(fc_parameters, {})

        # Test with KeyError in BATT_MONITOR_CONNECTION
        fc_parameters = {
            "BATT_MONITOR": 999999,  # Non-existent value
        }

        realistic_vehicle_data.process_fc_parameters(fc_parameters, {})

    def test_update_json_structure_with_existing_fc_data(self, realistic_vehicle_data) -> None:
        """Test update_json_structure when Flight Controller already has some data."""
        # Start with Flight Controller having some existing data
        realistic_vehicle_data.data["Components"]["Flight Controller"] = {
            "Product": {"Manufacturer": "Existing", "Model": "Model"},
            "Firmware": {"Type": "ArduCopter"},
            "Notes": "Existing notes",
        }

        realistic_vehicle_data.update_json_structure()

        # Should preserve existing data while adding Specifications
        fc_data = realistic_vehicle_data.data["Components"]["Flight Controller"]
        assert fc_data["Product"]["Manufacturer"] == "Existing"
        assert fc_data["Product"]["Model"] == "Model"
        assert fc_data["Firmware"]["Type"] == "ArduCopter"
        assert fc_data["Notes"] == "Existing notes"
        assert fc_data["Specifications"]["MCU Series"] == "Unknown"

    def test_update_json_structure_missing_fc_subkeys(self, realistic_vehicle_data) -> None:
        """Test update_json_structure when Flight Controller has missing sub-keys."""
        # Flight Controller exists but missing some keys
        realistic_vehicle_data.data["Components"]["Flight Controller"] = {
            "Product": {"Manufacturer": "Matek"},
            # Missing Firmware and Notes
        }

        realistic_vehicle_data.update_json_structure()

        fc_data = realistic_vehicle_data.data["Components"]["Flight Controller"]
        assert fc_data["Product"]["Manufacturer"] == "Matek"
        assert fc_data["Firmware"] == {}  # Should be empty dict for missing key
        assert fc_data["Notes"] == ""  # Should be empty string for missing key
        assert fc_data["Specifications"]["MCU Series"] == "Unknown"

    def test_gnss_connection_invalid_type(self, realistic_vehicle_data) -> None:
        """Test GNSS connection with invalid connection type."""
        # Mock a case where an unknown connection type is returned
        # This tests the else clause in _set_gnss_type_from_fc_parameters

        fc_parameters = {
            "GPS_TYPE": 999,  # Non-existent GPS type
        }

        realistic_vehicle_data.process_fc_parameters(fc_parameters, {})

        gnss_type = realistic_vehicle_data.get_component_value(("GNSS Receiver", "FC Connection", "Type"))
        assert gnss_type == "None"

    def test_multiple_esc_serial_connections(self, realistic_vehicle_data) -> None:
        """Test multiple ESC serial connections (should return True)."""
        fc_parameters = {
            "SERIAL1_PROTOCOL": 38,  # FETtecOneWire ESC
            "SERIAL2_PROTOCOL": 39,  # Torqeedo ESC (second ESC)
        }

        # The method should return True when esc >= 2
        esc_is_serial = realistic_vehicle_data._set_serial_type_from_fc_parameters(fc_parameters)
        assert esc_is_serial is True

    def test_voltage_validation_with_unknown_field(self, realistic_vehicle_data) -> None:
        """Test voltage validation with unknown voltage field."""
        # Test with a field that's not in the expected voltage fields
        is_valid, error, corrected = realistic_vehicle_data.validate_cell_voltage(
            "invalid_value", ("Battery", "Specifications", "Unknown Voltage Field"), "Lipo"
        )

        assert not is_valid
        assert "Invalid value" in error
        assert corrected == "3.8"  # Default fallback value
