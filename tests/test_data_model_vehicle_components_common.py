#!/usr/bin/env python3

"""
Common test utilities and fixtures for vehicle components data model tests.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import copy
from typing import Any, Optional, TypeVar, cast

from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents
from ardupilot_methodic_configurator.data_model_vehicle_components_json_schema import VehicleComponentsJsonSchema

# Type variables for generic fixture factories
T = TypeVar("T")

# Common test data structures
EMPTY_COMPONENT_DATA = {
    "Components": {},
    "Format version": 1,
}

BASIC_COMPONENT_DATA = {
    "Components": {
        "Battery": {"Specifications": {"Chemistry": "Lipo", "Capacity mAh": 0}},
        "Frame": {"Specifications": {"TOW min Kg": 1, "TOW max Kg": 1}},
        "Flight Controller": {"Product": {}, "Firmware": {}, "Specifications": {"MCU Series": "Unknown"}, "Notes": ""},
    },
    "Format version": 1,
    "Program version": "1.4.8",
}

# pylint: disable=duplicate-code
REALISTIC_VEHICLE_DATA = {
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
# pylint: enable=duplicate-code

SAMPLE_DOC_DICT = {
    "RC_PROTOCOLS": {"Bitmask": {"0": "All", "9": "CRSF", "11": "FPORT"}},
    "BATT_MONITOR": {"values": {"0": "Disabled", "4": "Analog Voltage and Current"}},
    "MOT_PWM_TYPE": {"values": {"0": "Normal", "6": "DShot600"}},
    "GPS_TYPE": {"values": {"0": "None", "2": "uBlox"}},
    "SERIAL1_PROTOCOL": {
        "values": {
            "1": "MAVLink1",
            "2": "MAVLink2",
            "5": "GPS",
            "23": "RCIN",
        }
    },
}


class ComponentDataModelFixtures:
    """Factory class for creating component data model fixtures."""

    @staticmethod
    def create_vehicle_components() -> VehicleComponents:
        """Create a VehicleComponents instance."""
        return VehicleComponents()

    @staticmethod
    def create_component_datatypes() -> dict[str, Any]:
        """Create component datatypes from schema."""
        vehicle_components = ComponentDataModelFixtures.create_vehicle_components()
        schema_dict = vehicle_components.load_schema()
        schema = VehicleComponentsJsonSchema(schema_dict)
        return schema.get_all_value_datatypes()

    @staticmethod
    def create_schema() -> VehicleComponentsJsonSchema:
        """Create a minimal schema for testing."""
        vehicle_components = ComponentDataModelFixtures.create_vehicle_components()
        schema_dict = vehicle_components.load_schema()
        return VehicleComponentsJsonSchema(schema_dict)

    @staticmethod
    def create_simple_schema() -> dict[str, Any]:
        """Create a simplified schema for testing."""
        return {
            "properties": {
                "Components": {
                    "properties": {
                        "Flight Controller": {
                            "description": "Flight controller component",
                            "properties": {
                                "Firmware": {
                                    "description": "Firmware information",
                                    "x-is-optional": True,
                                    "properties": {"Type": {"description": "Firmware type"}},
                                },
                                "Product": {"description": "Product information"},
                            },
                        }
                    }
                }
            },
            "definitions": {
                "product": {
                    "properties": {
                        "Manufacturer": {"description": "Manufacturer name", "x-is-optional": False},
                        "Model": {"description": "Model identifier", "x-is-optional": True},
                    }
                }
            },
        }

    @staticmethod
    def create_empty_model(model_class: type[T]) -> T:
        """Create an empty component data model."""
        data = copy.deepcopy(EMPTY_COMPONENT_DATA)
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = model_class(data, component_datatypes, schema)
        if hasattr(model, "post_init"):
            model.post_init({})
        return cast("T", model)

    @staticmethod
    def create_basic_model(model_class: type[T], data: Optional[dict[str, Any]] = None) -> T:
        """Create a basic component data model with simple data."""
        data = copy.deepcopy(data or BASIC_COMPONENT_DATA)
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = model_class(data, component_datatypes, schema)
        if hasattr(model, "post_init"):
            model.post_init({})
        return cast("T", model)

    @staticmethod
    def create_realistic_model(model_class: type[T]) -> T:
        """Create a realistic component data model with comprehensive data."""
        data = copy.deepcopy(REALISTIC_VEHICLE_DATA)
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = model_class(data, component_datatypes, schema)
        if hasattr(model, "post_init"):
            model.post_init({})
        return cast("T", model)


class CommonAssertions:
    """Common assertion helpers for component data model tests."""

    @staticmethod
    def assert_basic_structure(model) -> None:
        """Assert basic component data structure is valid."""
        data = model.get_component_data()
        assert isinstance(data, dict)
        assert "Components" in data
        assert isinstance(data["Components"], dict)
        assert "Format version" in data

    @staticmethod
    def assert_basic_components(model) -> None:
        """Assert basic auto-populated components are present and correct."""
        data = model.get_component_data()
        components = data["Components"]

        # Check auto-populated Battery component
        assert "Battery" in components
        assert components["Battery"]["Specifications"]["Chemistry"] == "Lipo"
        assert components["Battery"]["Specifications"]["Capacity mAh"] == 0

        # Check auto-populated Frame component
        assert "Frame" in components
        assert components["Frame"]["Specifications"]["TOW min Kg"] == 1
        assert components["Frame"]["Specifications"]["TOW max Kg"] == 1

        # Check auto-populated Flight Controller component
        assert "Flight Controller" in components
        assert components["Flight Controller"]["Specifications"]["MCU Series"] == "Unknown"
        assert components["Flight Controller"]["Product"] == {}
        assert components["Flight Controller"]["Firmware"] == {}
        assert components["Flight Controller"]["Notes"] == ""

    @staticmethod
    def assert_empty_components(model) -> None:
        """Assert model has minimal auto-populated components structure."""
        data = model.get_component_data()
        # After post_init, even "empty" models have auto-populated components
        # due to update_json_structure() ensuring backward compatibility
        expected_auto_components = {"Battery", "Frame", "Flight Controller"}
        actual_components = set(data["Components"].keys())

        # Check that only auto-populated components exist
        assert actual_components == expected_auto_components
        assert data["Format version"] == 1

    @staticmethod
    def assert_realistic_flight_controller(model) -> None:
        """Assert realistic flight controller data is present and correct."""
        components = model.get_component_data()["Components"]
        fc_data = components["Flight Controller"]
        assert fc_data["Product"]["Manufacturer"] == "Matek"
        assert fc_data["Product"]["Model"] == "H743 SLIM"
        assert fc_data["Firmware"]["Type"] == "ArduCopter"
        assert fc_data["Specifications"]["MCU Series"] == "STM32H7xx"

    @staticmethod
    def assert_realistic_frame_specs(model) -> None:
        """Assert realistic frame specifications are correct."""
        frame_tow_min = model.get_component_value(("Frame", "Specifications", "TOW min Kg"))
        frame_tow_max = model.get_component_value(("Frame", "Specifications", "TOW max Kg"))
        assert frame_tow_min == 0.6
        assert frame_tow_max == 0.6

    @staticmethod
    def assert_realistic_battery_specs(model) -> None:
        """Assert realistic battery specifications are correct."""
        components = model.get_component_data()["Components"]
        battery_specs = components["Battery"]["Specifications"]
        assert battery_specs["Chemistry"] == "Lipo"
        assert battery_specs["Number of cells"] == 4
        assert battery_specs["Capacity mAh"] == 1800
        assert battery_specs["Volt per cell max"] == 4.2

    @staticmethod
    def assert_realistic_motor_specs(model) -> None:
        """Assert realistic motor specifications are correct."""
        motor_poles = model.get_component_value(("Motors", "Specifications", "Poles"))
        assert motor_poles == 14


# Common test methods that can be mixed into test classes
class BasicTestMixin:
    """Mixin class providing common test methods for basic functionality."""

    def test_init_with_data(self, basic_model) -> None:
        """Test initialization with data."""
        CommonAssertions.assert_basic_structure(basic_model)
        CommonAssertions.assert_basic_components(basic_model)
        data = basic_model.get_component_data()
        assert data["Format version"] == 1

    def test_init_empty(self, empty_model) -> None:
        """Test initialization with no data."""
        CommonAssertions.assert_basic_structure(empty_model)
        CommonAssertions.assert_empty_components(empty_model)

    def test_get_component_data(self, basic_model) -> None:
        """Test getting component data."""
        CommonAssertions.assert_basic_structure(basic_model)

    def test_basic_component_data_structure(self, basic_model, empty_model) -> None:
        """Test basic component data structure validation."""
        CommonAssertions.assert_basic_structure(basic_model)
        CommonAssertions.assert_basic_structure(empty_model)

    def test_get_all_components(self, basic_model, empty_model) -> None:
        """Test getting all components."""
        # Test with basic model - should have auto-populated components
        components = basic_model.get_all_components()
        expected_auto_components = {"Battery", "Frame", "Flight Controller"}
        actual_components = set(components.keys())
        assert actual_components == expected_auto_components

        # Test with empty data - should have same auto-populated components
        empty_components = empty_model.get_all_components()
        assert set(empty_components.keys()) == expected_auto_components


class RealisticDataTestMixin:
    """Mixin class providing common test methods for realistic data functionality."""

    def test_realistic_vehicle_component_access(self, realistic_model) -> None:
        """Test accessing components from realistic vehicle data."""
        CommonAssertions.assert_realistic_flight_controller(realistic_model)
        CommonAssertions.assert_realistic_frame_specs(realistic_model)
        CommonAssertions.assert_realistic_battery_specs(realistic_model)
        CommonAssertions.assert_realistic_motor_specs(realistic_model)

    def test_has_components_check(self, realistic_model, empty_model) -> None:
        """Test checking if data model has components."""
        # Realistic data should have components
        assert realistic_model.has_components()

        # Empty data should have auto-populated components after post_init
        # so has_components() will return True
        assert empty_model.has_components()
        assert empty_model.has_components()
