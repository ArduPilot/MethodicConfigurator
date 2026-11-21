#!/usr/bin/env python3

"""
Common test utilities and fixtures for vehicle components data model tests.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import copy
from typing import Any, TypeVar
from unittest.mock import MagicMock

from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents
from ardupilot_methodic_configurator.data_model_vehicle_components_base import ComponentDataModelBase
from ardupilot_methodic_configurator.data_model_vehicle_components_display import ComponentDataModelDisplay
from ardupilot_methodic_configurator.data_model_vehicle_components_json_schema import VehicleComponentsJsonSchema

# Type variables for generic fixture factories
T = TypeVar("T", bound=ComponentDataModelBase)

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
            "Firmware": {"Type": "ArduCopter", "Version": "4.6.3"},
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
        "Battery Monitor": {
            "Product": {
                "Manufacturer": "None",
                "Model": "None",
                "URL": "",
                "Version": "",
            },
            "FC Connection": {"Type": "None", "Protocol": "None"},
            "Notes": "No battery monitor in this sample",
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
    # pylint: disable=duplicate-code  # Shared test fixture
    "SERIAL1_PROTOCOL": {
        "values": {
            "1": "MAVLink1",
            "2": "MAVLink2",
            "5": "GPS",
            "23": "RCIN",
        }
    },
    # pylint: enable=duplicate-code
}


def make_fc_schema(fc_body: dict[str, Any], *, definitions: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a minimal schema dict wrapping a single Flight Controller component body."""
    schema: dict[str, Any] = {"properties": {"Components": {"properties": {"Flight Controller": fc_body}}}}
    if definitions is not None:
        schema["definitions"] = definitions
    return schema


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
        return {  # pylint: disable=duplicate-code  # Minimal schema structure for tests
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
            # pylint: enable=duplicate-code
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
        post_init = getattr(model, "post_init", None)
        if callable(post_init):
            post_init({})
        return model

    @staticmethod
    def create_basic_model(model_class: type[T], data: dict[str, Any] | None = None) -> T:
        """Create a basic component data model with simple data."""
        data = copy.deepcopy(data or BASIC_COMPONENT_DATA)
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = model_class(data, component_datatypes, schema)
        post_init = getattr(model, "post_init", None)
        if callable(post_init):
            post_init({})
        return model

    @staticmethod
    def create_realistic_model(model_class: type[T]) -> T:
        """Create a realistic component data model with comprehensive data."""
        data = copy.deepcopy(REALISTIC_VEHICLE_DATA)
        component_datatypes = ComponentDataModelFixtures.create_component_datatypes()
        schema = ComponentDataModelFixtures.create_schema()
        model = model_class(data, component_datatypes, schema)
        post_init = getattr(model, "post_init", None)
        if callable(post_init):
            post_init({})
        return model

    @staticmethod
    def create_mock_schema() -> MagicMock:
        """Create a mock schema with default non-optional behavior."""
        schema = MagicMock()
        schema.get_component_property_description.return_value = ("Test description", False)
        return schema

    @staticmethod
    def create_display_model_with_mock_schema(mock_schema: MagicMock) -> ComponentDataModelDisplay:
        """Create a ComponentDataModelDisplay instance backed by a mock schema."""
        initial_data: dict[str, Any] = {"Components": {}, "Format version": 1}
        component_datatypes: dict[str, Any] = {"Flight Controller": {"Product": {"Manufacturer": str}}}
        schema_dict = ComponentDataModelFixtures.create_simple_schema()
        schema = VehicleComponentsJsonSchema(schema_dict)
        model = ComponentDataModelDisplay(initial_data, component_datatypes, schema)
        model.schema = mock_schema
        return model
