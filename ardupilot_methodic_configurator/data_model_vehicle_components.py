#!/usr/bin/env python3

"""
Data model for vehicle components.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# from logging import debug as logging_debug
from logging import error as logging_error
from math import log2
from types import MappingProxyType
from typing import Any, Union

from ardupilot_methodic_configurator import _, __version__
from ardupilot_methodic_configurator.backend_filesystem import LocalFilesystem
from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents
from ardupilot_methodic_configurator.battery_cell_voltages import BatteryCell

# Type aliases to improve code readability
ComponentPath = tuple[str, ...]
ComponentData = dict[str, Any]
ComponentValue = Union[str, int, float]
ValidationRulePath = tuple[str, str, str]  # Exactly 3 elements for validation rules

# Port definitions
ANALOG_PORTS = ["Analog"]
SERIAL_PORTS = ["SERIAL1", "SERIAL2", "SERIAL3", "SERIAL4", "SERIAL5", "SERIAL6", "SERIAL7", "SERIAL8"]
CAN_PORTS = ["CAN1", "CAN2"]
I2C_PORTS = ["I2C1", "I2C2", "I2C3", "I2C4"]
PWM_PORTS = ["Main Out", "AIO"]
RC_PORTS = ["RCin/SBUS"]

# Protocol dictionaries
SERIAL_PROTOCOLS_DICT: dict[str, dict[str, Any]] = {
    "-1": {"type": SERIAL_PORTS, "protocol": "None", "component": None},
    "1": {"type": SERIAL_PORTS, "protocol": "MAVLink1", "component": "Telemetry"},
    "2": {"type": SERIAL_PORTS, "protocol": "MAVLink2", "component": "Telemetry"},
    "3": {"type": SERIAL_PORTS, "protocol": "Frsky D", "component": None},
    "4": {"type": SERIAL_PORTS, "protocol": "Frsky SPort", "component": None},
    "5": {"type": SERIAL_PORTS, "protocol": "GPS", "component": "GNSS Receiver"},
    "7": {"type": SERIAL_PORTS, "protocol": "Alexmos Gimbal Serial", "component": None},
    "8": {"type": SERIAL_PORTS, "protocol": "Gimbal", "component": None},
    "9": {"type": SERIAL_PORTS, "protocol": "Rangefinder", "component": None},
    "10": {"type": SERIAL_PORTS, "protocol": "FrSky SPort Passthrough (OpenTX)", "component": None},
    "11": {"type": SERIAL_PORTS, "protocol": "Lidar360", "component": None},
    "13": {"type": SERIAL_PORTS, "protocol": "Beacon", "component": None},
    "14": {"type": SERIAL_PORTS, "protocol": "Volz servo out", "component": None},
    "15": {"type": SERIAL_PORTS, "protocol": "SBus servo out", "component": None},
    "16": {"type": SERIAL_PORTS, "protocol": "ESC Telemetry", "component": None},
    "17": {"type": SERIAL_PORTS, "protocol": "Devo Telemetry", "component": None},
    "18": {"type": SERIAL_PORTS, "protocol": "OpticalFlow", "component": None},
    "19": {"type": SERIAL_PORTS, "protocol": "RobotisServo", "component": None},
    "20": {"type": SERIAL_PORTS, "protocol": "NMEA Output", "component": None},
    "21": {"type": SERIAL_PORTS, "protocol": "WindVane", "component": None},
    "22": {"type": SERIAL_PORTS, "protocol": "SLCAN", "component": None},
    "23": {"type": SERIAL_PORTS, "protocol": "RCIN", "component": "RC Receiver"},
    "24": {"type": SERIAL_PORTS, "protocol": "EFI Serial", "component": None},
    "25": {"type": SERIAL_PORTS, "protocol": "LTM", "component": None},
    "26": {"type": SERIAL_PORTS, "protocol": "RunCam", "component": None},
    "27": {"type": SERIAL_PORTS, "protocol": "HottTelem", "component": None},
    "28": {"type": SERIAL_PORTS, "protocol": "Scripting", "component": None},
    "29": {"type": SERIAL_PORTS, "protocol": "Crossfire VTX", "component": None},
    "30": {"type": SERIAL_PORTS, "protocol": "Generator", "component": None},
    "31": {"type": SERIAL_PORTS, "protocol": "Winch", "component": None},
    "32": {"type": SERIAL_PORTS, "protocol": "MSP", "component": None},
    "33": {"type": SERIAL_PORTS, "protocol": "DJI FPV", "component": None},
    "34": {"type": SERIAL_PORTS, "protocol": "AirSpeed", "component": None},
    "35": {"type": SERIAL_PORTS, "protocol": "ADSB", "component": None},
    "36": {"type": SERIAL_PORTS, "protocol": "AHRS", "component": None},
    "37": {"type": SERIAL_PORTS, "protocol": "SmartAudio", "component": None},
    "38": {"type": SERIAL_PORTS, "protocol": "FETtecOneWire", "component": "ESC"},
    "39": {"type": SERIAL_PORTS, "protocol": "Torqeedo", "component": "ESC"},
    "40": {"type": SERIAL_PORTS, "protocol": "AIS", "component": None},
    "41": {"type": SERIAL_PORTS, "protocol": "CoDevESC", "component": "ESC"},
    "42": {"type": SERIAL_PORTS, "protocol": "DisplayPort", "component": None},
    "43": {"type": SERIAL_PORTS, "protocol": "MAVLink High Latency", "component": "Telemetry"},
    "44": {"type": SERIAL_PORTS, "protocol": "IRC Tramp", "component": None},
    "45": {"type": SERIAL_PORTS, "protocol": "DDS XRCE", "component": None},
    "46": {"type": SERIAL_PORTS, "protocol": "IMUDATA", "component": None},
}

BATT_MONITOR_CONNECTION: dict[str, dict[str, str]] = {
    "0": {"type": "None", "protocol": "Disabled"},
    "3": {"type": "Analog", "protocol": "Analog Voltage Only"},
    "4": {"type": "Analog", "protocol": "Analog Voltage and Current"},
    "5": {"type": "i2c", "protocol": "Solo"},
    "6": {"type": "i2c", "protocol": "Bebop"},
    "7": {"type": "i2c", "protocol": "SMBus-Generic"},
    "8": {"type": "can", "protocol": "DroneCAN-BatteryInfo"},
    "9": {"type": "None", "protocol": "ESC"},
    "10": {"type": "None", "protocol": "Sum Of Selected Monitors"},
    "11": {"type": "i2c", "protocol": "FuelFlow"},
    "12": {"type": "pwm", "protocol": "FuelLevelPWM"},
    "13": {"type": "i2c", "protocol": "SMBUS-SUI3"},
    "14": {"type": "i2c", "protocol": "SMBUS-SUI6"},
    "15": {"type": "i2c", "protocol": "NeoDesign"},
    "16": {"type": "i2c", "protocol": "SMBus-Maxell"},
    "17": {"type": "i2c", "protocol": "Generator-Elec"},
    "18": {"type": "i2c", "protocol": "Generator-Fuel"},
    "19": {"type": "i2c", "protocol": "Rotoye"},
    "20": {"type": "i2c", "protocol": "MPPT"},
    "21": {"type": "i2c", "protocol": "INA2XX"},
    "22": {"type": "i2c", "protocol": "LTC2946"},
    "23": {"type": "None", "protocol": "Torqeedo"},
    "24": {"type": "Analog", "protocol": "FuelLevelAnalog"},
    "25": {"type": "Analog", "protocol": "Synthetic Current and Analog Voltage"},
    "26": {"type": "spi", "protocol": "INA239_SPI"},
    "27": {"type": "i2c", "protocol": "EFI"},
    "28": {"type": "i2c", "protocol": "AD7091R5"},
    "29": {"type": "None", "protocol": "Scripting"},
}

GNSS_RECEIVER_CONNECTION: dict[str, Any] = {
    "0": {"type": None, "protocol": "None"},
    "1": {"type": "serial", "protocol": "AUTO"},
    "2": {"type": "serial", "protocol": "uBlox"},
    "5": {"type": "serial", "protocol": "NMEA"},
    "6": {"type": "serial", "protocol": "SiRF"},
    "7": {"type": "serial", "protocol": "HIL"},
    "8": {"type": "serial", "protocol": "SwiftNav"},
    "9": {"type": "can", "protocol": "DroneCAN"},
    "10": {"type": "serial", "protocol": "SBF"},
    "11": {"type": "serial", "protocol": "GSOF"},
    "13": {"type": "serial", "protocol": "ERB"},
    "14": {"type": "serial", "protocol": "MAV"},
    "15": {"type": "serial", "protocol": "NOVA"},
    "16": {"type": "serial", "protocol": "HemisphereNMEA"},
    "17": {"type": "serial", "protocol": "uBlox-MovingBaseline-Base"},
    "18": {"type": "serial", "protocol": "uBlox-MovingBaseline-Rover"},
    "19": {"type": "serial", "protocol": "MSP"},
    "20": {"type": "serial", "protocol": "AllyStar"},
    "21": {"type": "serial", "protocol": "ExternalAHRS"},
    "22": {"type": "can", "protocol": "DroneCAN-MovingBaseline-Base"},
    "23": {"type": "can", "protocol": "DroneCAN-MovingBaseline-Rover"},
    "24": {"type": "serial", "protocol": "UnicoreNMEA"},
    "25": {"type": "serial", "protocol": "UnicoreMovingBaselineNMEA"},
    "26": {"type": "serial", "protocol": "SBF-DualAntenna"},
}

MOT_PWM_TYPE_DICT: dict[str, dict[str, Any]] = {
    "0": {"type": "Main Out", "protocol": "Normal", "is_dshot": False},
    "1": {"type": "Main Out", "protocol": "OneShot", "is_dshot": True},
    "2": {"type": "Main Out", "protocol": "OneShot125", "is_dshot": True},
    "3": {"type": "Main Out", "protocol": "Brushed", "is_dshot": False},
    "4": {"type": "Main Out", "protocol": "DShot150", "is_dshot": True},
    "5": {"type": "Main Out", "protocol": "DShot300", "is_dshot": True},
    "6": {"type": "Main Out", "protocol": "DShot600", "is_dshot": True},
    "7": {"type": "Main Out", "protocol": "DShot1200", "is_dshot": True},
    "8": {"type": "Main Out", "protocol": "PWMRange", "is_dshot": False},
}

RC_PROTOCOLS_DICT: dict[str, dict[str, str]] = {
    "0": {"type": "RCin/SBUS", "protocol": "All"},
    "1": {"type": "RCin/SBUS", "protocol": "PPM"},
    "2": {"type": "RCin/SBUS", "protocol": "IBUS"},
    "3": {"type": "RCin/SBUS", "protocol": "SBUS"},
    "4": {"type": "RCin/SBUS", "protocol": "SBUS_NI"},
    "5": {"type": "RCin/SBUS", "protocol": "DSM"},
    "6": {"type": "RCin/SBUS", "protocol": "SUMD"},
    "7": {"type": "RCin/SBUS", "protocol": "SRXL"},
    "8": {"type": "RCin/SBUS", "protocol": "SRXL2"},
    "9": {"type": "RCin/SBUS", "protocol": "CRSF"},
    "10": {"type": "RCin/SBUS", "protocol": "ST24"},
    "11": {"type": "RCin/SBUS", "protocol": "FPORT"},
    "12": {"type": "RCin/SBUS", "protocol": "FPORT2"},
    "13": {"type": "RCin/SBUS", "protocol": "FastSBUS"},
    "14": {"type": "can", "protocol": "DroneCAN"},
    "15": {"type": "RCin/SBUS", "protocol": "Ghost"},
}


class ComponentDataModel:  # pylint: disable=too-many-public-methods
    """
    A class to handle component data operations separate from UI logic.

    This improves testability by isolating data operations.
    """

    # Class attribute for validation rules - use immutable mapping
    VALIDATION_RULES: MappingProxyType[ValidationRulePath, tuple[type, tuple[float, float], str]] = MappingProxyType(
        {
            ("Frame", "Specifications", "TOW min Kg"): (float, (0.01, 600), "Takeoff Weight"),
            ("Frame", "Specifications", "TOW max Kg"): (float, (0.01, 600), "Takeoff Weight"),
            ("Battery", "Specifications", "Number of cells"): (int, (1, 50), "Nr of cells"),
            ("Battery", "Specifications", "Capacity mAh"): (int, (100, 1000000), "mAh capacity"),
            ("Motors", "Specifications", "Poles"): (int, (3, 50), "Motor Poles"),
            ("Propellers", "Specifications", "Diameter_inches"): (float, (0.3, 400), "Propeller Diameter"),
        }
    )

    def __init__(self, initial_data: ComponentData) -> None:
        self.data: ComponentData = initial_data if initial_data else {"Components": {}, "Format version": 1}

    def get_component_data(self) -> ComponentData:
        """
        Get the complete component data.

        Only used in pytest code
        """
        return self.data

    def ensure_format_version(self) -> None:
        """Ensure the format version is set."""
        if "Format version" not in self.data:
            self.data["Format version"] = 1

    def set_component_value(self, path: ComponentPath, value: Union[ComponentData, ComponentValue, None]) -> None:
        """Set a specific component value in the data structure."""
        if value is None:
            value = ""
        data_path: ComponentData = self.data["Components"]

        # Navigate to the correct place in the data structure
        for key in path[:-1]:
            if key not in data_path:
                data_path[key] = {}
            data_path = data_path[key]

        # Update the value
        data_path[path[-1]] = value

    def get_component_value(self, path: ComponentPath) -> Union[ComponentData, ComponentValue]:
        """Get a specific component value from the data structure."""
        data_path = self.data["Components"]
        for key in path:
            if key not in data_path:
                empty_dict: dict[str, Any] = {}
                return empty_dict
            data_path = data_path[key]

        # Ensure we return a value that matches our ComponentValue type
        if isinstance(data_path, (str, int, float, dict)):
            return data_path
        # If it's some other type, convert to string
        return str(data_path)

    def _process_value(self, path: ComponentPath, value: Union[str, None]) -> ComponentValue:
        """Process a string value into the appropriate type based on context."""
        # Handle None value
        if value is None:
            return ""

        # Special handling for Version fields
        if path[-1] != "Version":
            try:
                return int(value)
            except ValueError:
                try:
                    return float(value)
                except ValueError:
                    return str(value).strip()
        return str(value).strip()

    def set_configuration_template(self, template_name: str) -> None:
        """Set the configuration template name in the data."""
        self.data["Configuration template"] = template_name

    def get_component(self, component_name: str) -> dict[str, Union[ComponentData, ComponentValue]]:
        """Get the data for a specific component."""
        if "Components" in self.data and component_name in self.data["Components"]:
            return self.data["Components"][component_name]  # type: ignore[no-any-return]
        return {}

    def update_component(self, component_name: str, component_data: dict) -> None:
        """Update a component with new data."""
        if "Components" not in self.data:
            self.data["Components"] = {}
        self.data["Components"][component_name] = component_data

    def derive_initial_template_name(self, component_data: dict[str, Any]) -> str:
        """Derive an initial template name from the component data."""
        initial_template_name: str = ""
        product_data = component_data.get("Product")
        if product_data:
            manufacturer = product_data.get("Manufacturer", "")
            model = product_data.get("Model", "")
            initial_template_name = manufacturer + " " + model
        return initial_template_name

    def extract_component_data_from_entries(self, component_name: str, entries: dict[ComponentPath, str]) -> dict:
        """
        Extract component data for a specific component from entries.

        This extracts and processes component data from entry values,
        organizing them into a properly structured dictionary.
        """
        component_data: ComponentData = {}

        # Find all entries belonging to this component and extract their values
        for path, value in entries.items():
            if len(path) >= 1 and path[0] == component_name:
                # Process the value based on type
                processed_value = self._process_value(path, value)

                # Create the nested structure
                current_level: ComponentData = component_data
                for key in path[1:-1]:  # Skip component_name and the last key
                    if key not in current_level:
                        current_level[key] = {}
                    current_level = current_level[key]

                # Set the value at the final level
                current_level[path[-1]] = processed_value

        return component_data

    def get_all_components(self) -> ComponentData:
        """Get all components data."""
        empty_dict: ComponentData = {}
        return self.data.get("Components", empty_dict)  # type: ignore[no-any-return]

    def is_valid_component_data(self) -> bool:
        """
        Validate the component data structure.

        Performs basic validation to ensure the data has the expected format.
        """
        return isinstance(self.data, dict) and "Components" in self.data and isinstance(self.data["Components"], dict)

    def has_components(self) -> bool:
        """Check if there are any components in the data."""
        return len(self.get_all_components()) >= 1

    def _update_from_entries(self, entries: dict[ComponentPath, str]) -> None:
        """Update the data model from entry widget values."""
        for path, value in entries.items():
            # Process the value based on type
            processed_value = self._process_value(path, value)
            self.set_component_value(path, processed_value)

    def save_to_filesystem(self, filesystem: LocalFilesystem, entry_values: dict[ComponentPath, str]) -> tuple[bool, str]:
        """Save component data to filesystem - centralizes save logic."""
        # Update the data model with entry values
        self._update_from_entries(entry_values)

        return filesystem.save_vehicle_components_json_data(self.get_component_data(), filesystem.vehicle_dir)

    def update_json_structure(self) -> None:
        """
        Update the data structure to ensure all required fields are present.

        Used to update old JSON files to the latest format.
        """
        # Get current data
        data = self.data

        # To update old JSON files that do not have these new fields
        if "Components" not in data:
            data["Components"] = {}

        if "Battery" not in data["Components"]:
            data["Components"]["Battery"] = {}

        if "Specifications" not in data["Components"]["Battery"]:
            data["Components"]["Battery"]["Specifications"] = {}

        if "Chemistry" not in data["Components"]["Battery"]["Specifications"]:
            data["Components"]["Battery"]["Specifications"]["Chemistry"] = "Lipo"

        if "Capacity mAh" not in data["Components"]["Battery"]["Specifications"]:
            data["Components"]["Battery"]["Specifications"]["Capacity mAh"] = 0

        # To update old JSON files that do not have these new "Frame.Specifications.TOW * Kg" fields
        if "Frame" not in data["Components"]:
            data["Components"]["Frame"] = {}

        if "Specifications" not in data["Components"]["Frame"]:
            data["Components"]["Frame"]["Specifications"] = {}

        if "TOW min Kg" not in data["Components"]["Frame"]["Specifications"]:
            data["Components"]["Frame"]["Specifications"]["TOW min Kg"] = 1

        if "TOW max Kg" not in data["Components"]["Frame"]["Specifications"]:
            data["Components"]["Frame"]["Specifications"]["TOW max Kg"] = 1

        # Older versions used receiver instead of Receiver, rename it for consistency with other fields
        if "GNSS receiver" in data["Components"]:
            data["Components"]["GNSS Receiver"] = data["Components"].pop("GNSS receiver")

        data["Program version"] = __version__

        # To update old JSON files that do not have this new "Flight Controller.Specifications.MCU Series" field
        if "Flight Controller" not in data["Components"]:
            data["Components"]["Flight Controller"] = {}

        if "Specifications" not in data["Components"]["Flight Controller"]:
            fc_data = data["Components"]["Flight Controller"]
            data["Components"]["Flight Controller"] = {
                "Product": fc_data.get("Product", {}),
                "Firmware": fc_data.get("Firmware", {}),
                "Specifications": {"MCU Series": "Unknown"},
                "Notes": fc_data.get("Notes", ""),
            }

    def is_fc_manufacturer_valid(self, manufacturer: str) -> bool:
        """Is flight controller manufacturer data valid."""
        return bool(manufacturer and manufacturer not in (_("Unknown"), "ArduPilot"))

    def is_fc_model_valid(self, model: str) -> bool:
        """Is flight controller model data valid."""
        return bool(model and model not in (_("Unknown"), "MAVLink"))

    @staticmethod
    def _reverse_key_search(
        doc: dict[str, dict[str, dict[str, float]]], param_name: str, values: list[float], fallbacks: list[int]
    ) -> list[int]:
        """
        Search for keys in documentation that have specified values.

        Used to find parameter keys from parameter values.
        """
        retv = [int(key) for key, value in doc[param_name]["values"].items() if value in values]
        if len(values) != len(fallbacks):
            logging_error(_("Length of values %u and fallbacks %u differ for %s"), len(values), len(fallbacks), param_name)
        if retv:
            return retv
        logging_error(_("No values found for %s in the metadata"), param_name)
        return fallbacks

    def _verify_dict_is_uptodate(self, doc: dict, dict_to_check: dict, doc_key: str, doc_dict: str) -> bool:
        """
        Verify that a dictionary is up-to-date with the apm.pdef.xml documentation metadata.

        Returns True if valid, False if there are discrepancies.
        """
        is_valid = True
        if not doc or doc_key not in doc or not doc[doc_key] or doc_dict not in doc[doc_key]:
            return False

        for key, doc_protocol in doc[doc_key][doc_dict].items():
            if key in dict_to_check:
                code_protocol = dict_to_check[key].get("protocol", None)
                if code_protocol != doc_protocol:
                    logging_error(_("Protocol %s does not match %s in %s metadata"), code_protocol, doc_protocol, doc_key)
                    is_valid = False
            else:
                logging_error(_("Protocol %s not found in %s metadata"), doc_protocol, doc_key)
                is_valid = False
        return is_valid

    def process_fc_parameters(
        self,
        fc_parameters: dict,
        doc: dict,
    ) -> None:
        """
        Process flight controller parameters and update the data model accordingly.

        This method consolidates all parameter processing logic in one place.
        """
        # First verify dictionaries match documentation
        self._verify_dict_is_uptodate(doc, SERIAL_PROTOCOLS_DICT, "SERIAL1_PROTOCOL", "values")
        self._verify_dict_is_uptodate(doc, BATT_MONITOR_CONNECTION, "BATT_MONITOR", "values")
        self._verify_dict_is_uptodate(doc, GNSS_RECEIVER_CONNECTION, "GPS_TYPE", "values")
        self._verify_dict_is_uptodate(doc, MOT_PWM_TYPE_DICT, "MOT_PWM_TYPE", "values")
        self._verify_dict_is_uptodate(doc, RC_PROTOCOLS_DICT, "RC_PROTOCOLS", "Bitmask")

        # Process parameters in sequence
        self._set_gnss_type_from_fc_parameters(fc_parameters)
        esc_is_serial = self._set_serial_type_from_fc_parameters(fc_parameters)
        if not esc_is_serial:
            self._set_esc_type_from_fc_parameters(fc_parameters, doc)

        self._set_battery_type_from_fc_parameters(fc_parameters)
        self._set_motor_poles_from_fc_parameters(fc_parameters)

    def _set_gnss_type_from_fc_parameters(self, fc_parameters: dict) -> None:
        """Process GNSS receiver parameters and update the data model."""
        gps1_type = fc_parameters.get("GPS_TYPE", 0)
        try:
            gps1_type = int(gps1_type)
        except (ValueError, TypeError):
            logging_error(_("Invalid non-integer value for GPS_TYPE %s"), gps1_type)
            gps1_type = 0

        if str(gps1_type) in GNSS_RECEIVER_CONNECTION:
            gps1_connection_type = GNSS_RECEIVER_CONNECTION[str(gps1_type)].get("type")
            gps1_connection_protocol = GNSS_RECEIVER_CONNECTION[str(gps1_type)].get("protocol")
            if gps1_connection_type is None:
                self.set_component_value(("GNSS Receiver", "FC Connection", "Type"), "None")
                self.set_component_value(("GNSS Receiver", "FC Connection", "Protocol"), "None")
            elif gps1_connection_type == "serial":
                # GNSS connection type will be detected later in set_serial_type_from_fc_parameters
                self.set_component_value(("GNSS Receiver", "FC Connection", "Protocol"), gps1_connection_protocol)
            elif gps1_connection_type == "can":
                if (
                    "CAN_D1_PROTOCOL" in fc_parameters
                    and fc_parameters["CAN_D1_PROTOCOL"] == 1
                    and "CAN_P1_DRIVER" in fc_parameters
                    and fc_parameters["CAN_P1_DRIVER"] == 1
                ):
                    self.set_component_value(("GNSS Receiver", "FC Connection", "Type"), "CAN1")
                elif (
                    "CAN_D2_PROTOCOL" in fc_parameters
                    and fc_parameters["CAN_D2_PROTOCOL"] == 1
                    and "CAN_P2_DRIVER" in fc_parameters
                    and fc_parameters["CAN_P2_DRIVER"] == 2
                ):
                    self.set_component_value(("GNSS Receiver", "FC Connection", "Type"), "CAN2")
                else:
                    logging_error(
                        _("Invalid CAN_Dx_PROTOCOL %s and CAN_Px_DRIVER %s for GNSS Receiver"),
                        fc_parameters.get("CAN_D1_PROTOCOL"),
                        fc_parameters.get("CAN_P1_DRIVER"),
                    )
                    self.set_component_value(("GNSS Receiver", "FC Connection", "Type"), "None")
                self.set_component_value(("GNSS Receiver", "FC Connection", "Protocol"), gps1_connection_protocol)
            else:
                logging_error("Invalid GNSS connection type %s", gps1_connection_type)
                self.set_component_value(("GNSS Receiver", "FC Connection", "Type"), "None")
        else:
            logging_error("GPS_TYPE %u not in GNSS_RECEIVER_CONNECTION", gps1_type)
            self.set_component_value(("GNSS Receiver", "FC Connection", "Type"), "None")

    def _set_serial_type_from_fc_parameters(self, fc_parameters: dict) -> bool:  # pylint: disable=too-many-branches
        """Process serial port parameters and update the data model. Returns True if ESC is serial controlled."""
        if "RC_PROTOCOLS" in fc_parameters:
            try:
                rc_protocols_nr = int(fc_parameters["RC_PROTOCOLS"])
            except (ValueError, TypeError):
                logging_error(_("Invalid non-integer value for RC_PROTOCOLS %s"), fc_parameters["RC_PROTOCOLS"])
                rc_protocols_nr = 0
            # check if rc_protocols_nr is a power of two (only one bit set) and not zero
            if rc_protocols_nr > 0 and rc_protocols_nr & (rc_protocols_nr - 1) == 0:
                # rc_bit is the number of the bit that is set
                rc_bit = str(int(log2(rc_protocols_nr)))
                protocol = RC_PROTOCOLS_DICT[rc_bit].get("protocol")
                self.set_component_value(("RC Receiver", "FC Connection", "Protocol"), protocol)

        rc = 1
        telem = 1
        gnss = 1
        esc = 1
        for serial in SERIAL_PORTS:
            if serial + "_PROTOCOL" not in fc_parameters:
                continue
            serial_protocol_nr = 0
            try:
                serial_protocol_nr = int(fc_parameters[serial + "_PROTOCOL"])
            except (ValueError, TypeError):
                msg = _("Invalid non-integer value for {serial}_PROTOCOL {serial_protocol_nr}")
                logging_error(msg.format(serial=serial, serial_protocol_nr=fc_parameters[serial + "_PROTOCOL"]))
                continue

            if serial_protocol_nr == 0:
                continue  # zero is an invalid protocol

            index_str = str(serial_protocol_nr)
            if index_str not in SERIAL_PROTOCOLS_DICT:
                continue

            component = SERIAL_PROTOCOLS_DICT[index_str].get("component")
            protocol = SERIAL_PROTOCOLS_DICT[index_str].get("protocol")
            if component is None:
                continue

            if component == "RC Receiver" and rc == 1:
                self.set_component_value(("RC Receiver", "FC Connection", "Type"), serial)
                rc += 1
            elif component == "Telemetry" and telem == 1:
                self.set_component_value(("Telemetry", "FC Connection", "Type"), serial)
                self.set_component_value(("Telemetry", "FC Connection", "Protocol"), protocol)
                telem += 1
            elif component == "GNSS Receiver" and gnss == 1:
                self.set_component_value(("GNSS Receiver", "FC Connection", "Type"), serial)
                gnss += 1
            elif component == "ESC":
                if esc == 1:
                    # Only set component values for the first ESC
                    self.set_component_value(("ESC", "FC Connection", "Type"), serial)
                    self.set_component_value(("ESC", "FC Connection", "Protocol"), protocol)
                # Count all ESC components
                esc += 1

        return esc >= 2

    def _set_esc_type_from_fc_parameters(self, fc_parameters: dict, doc: dict) -> None:
        """Process ESC parameters and update the data model."""
        mot_pwm_type = fc_parameters.get("MOT_PWM_TYPE", 0)
        try:
            mot_pwm_type = int(mot_pwm_type)
        except (ValueError, TypeError):
            logging_error(_("Invalid non-integer value for MOT_PWM_TYPE %s"), mot_pwm_type)
            mot_pwm_type = 0

        main_out_functions = [fc_parameters.get("SERVO" + str(i) + "_FUNCTION", 0) for i in range(1, 9)]

        # if any element of main_out_functions is in [33, 34, 35, 36] then ESC is connected to main_out
        if any(servo_function in {33, 34, 35, 36} for servo_function in main_out_functions):
            self.set_component_value(("ESC", "FC Connection", "Type"), "Main Out")
        else:
            self.set_component_value(("ESC", "FC Connection", "Type"), "AIO")

        if "MOT_PWM_TYPE" in doc and "values" in doc["MOT_PWM_TYPE"]:
            protocol = doc["MOT_PWM_TYPE"]["values"].get(str(mot_pwm_type))
            if protocol:
                self.set_component_value(("ESC", "FC Connection", "Protocol"), protocol)
        # Fallback to MOT_PWM_TYPE_DICT if doc is not available
        elif str(mot_pwm_type) in MOT_PWM_TYPE_DICT:
            protocol = MOT_PWM_TYPE_DICT[str(mot_pwm_type)]["protocol"]
            self.set_component_value(("ESC", "FC Connection", "Protocol"), protocol)

    def _set_battery_type_from_fc_parameters(self, fc_parameters: dict) -> None:
        """Process battery monitor parameters and update the data model."""
        if "BATT_MONITOR" in fc_parameters:
            try:
                batt_monitor = int(fc_parameters["BATT_MONITOR"])
                batt_type = BATT_MONITOR_CONNECTION[str(batt_monitor)].get("type", "None")
                batt_protocol = BATT_MONITOR_CONNECTION[str(batt_monitor)].get("protocol", "Disabled")

                self.set_component_value(("Battery Monitor", "FC Connection", "Type"), batt_type)
                self.set_component_value(("Battery Monitor", "FC Connection", "Protocol"), batt_protocol)
            except (ValueError, KeyError, TypeError) as e:
                logging_error(_("Error processing BATT_MONITOR parameter: %s"), str(e))

    def _set_motor_poles_from_fc_parameters(self, fc_parameters: dict) -> None:
        """Process motor parameters and update the data model."""
        if "MOT_PWM_TYPE" in fc_parameters:
            mot_pwm_type_str = str(fc_parameters["MOT_PWM_TYPE"])
            if mot_pwm_type_str in MOT_PWM_TYPE_DICT and MOT_PWM_TYPE_DICT[mot_pwm_type_str].get("is_dshot", False):
                if "SERVO_BLH_POLES" in fc_parameters:
                    self.set_component_value(("Motors", "Specifications", "Poles"), fc_parameters["SERVO_BLH_POLES"])
            elif "SERVO_FTW_MASK" in fc_parameters and fc_parameters["SERVO_FTW_MASK"] and "SERVO_FTW_POLES" in fc_parameters:
                self.set_component_value(("Motors", "Specifications", "Poles"), fc_parameters["SERVO_FTW_POLES"])

    def get_esc_protocol_values(self, esc_connection_type: str, doc_dict: dict) -> list[str]:
        """Get ESC protocol values based on connection type."""
        if len(esc_connection_type) > 3 and esc_connection_type[:3] == "CAN":
            return ["DroneCAN"]
        if len(esc_connection_type) > 6 and esc_connection_type[:6] == "SERIAL":
            return [value["protocol"] for value in SERIAL_PROTOCOLS_DICT.values() if value["component"] == "ESC"]
        if "MOT_PWM_TYPE" in doc_dict:
            return list(doc_dict["MOT_PWM_TYPE"]["values"].values())
        if "Q_M_PWM_TYPE" in doc_dict:
            return list(doc_dict["Q_M_PWM_TYPE"]["values"].values())
        return []

    def get_combobox_values_for_path(self, path: ValidationRulePath, doc_dict: dict) -> tuple[str, ...]:
        """Get valid combobox values for a given path."""
        # Default values for comboboxes in case the apm.pdef.xml metadata is not available
        fallbacks: dict[str, tuple[str, ...]] = {
            "RC_PROTOCOLS": tuple(value["protocol"] for value in RC_PROTOCOLS_DICT.values()),
            "BATT_MONITOR": tuple(value["protocol"] for value in BATT_MONITOR_CONNECTION.values()),
            "MOT_PWM_TYPE": tuple(value["protocol"] for value in MOT_PWM_TYPE_DICT.values()),
            "GPS_TYPE": tuple(value["protocol"] for value in GNSS_RECEIVER_CONNECTION.values()),
        }

        def get_combobox_values(param_name: str) -> tuple[str, ...]:
            if param_name in doc_dict:
                if "values" in doc_dict[param_name] and doc_dict[param_name]["values"]:
                    return tuple(doc_dict[param_name]["values"].values())
                if "Bitmask" in doc_dict[param_name] and doc_dict[param_name]["Bitmask"]:
                    return tuple(doc_dict[param_name]["Bitmask"].values())
                logging_error(_("No values found for %s in the metadata"), param_name)
            if param_name in fallbacks:
                return fallbacks[param_name]
            logging_error(_("No fallback values found for %s"), param_name)
            return ()

        combobox_dict: dict[ValidationRulePath, tuple[str, ...]] = {
            ("Flight Controller", "Firmware", "Type"): VehicleComponents.supported_vehicles(),
            ("RC Receiver", "FC Connection", "Type"): ("RCin/SBUS", *SERIAL_PORTS, *CAN_PORTS),
            ("RC Receiver", "FC Connection", "Protocol"): get_combobox_values("RC_PROTOCOLS"),
            ("Telemetry", "FC Connection", "Type"): tuple(SERIAL_PORTS + CAN_PORTS),
            ("Telemetry", "FC Connection", "Protocol"): ("MAVLink1", "MAVLink2", "MAVLink High Latency"),
            ("Battery Monitor", "FC Connection", "Type"): (
                "None",
                "Analog",
                "SPI",
                "PWM",
                *I2C_PORTS,
                *SERIAL_PORTS,
                *CAN_PORTS,
            ),
            ("Battery Monitor", "FC Connection", "Protocol"): get_combobox_values("BATT_MONITOR"),
            ("ESC", "FC Connection", "Type"): ("Main Out", "AIO", *SERIAL_PORTS, *CAN_PORTS),
            ("ESC", "FC Connection", "Protocol"): get_combobox_values("MOT_PWM_TYPE"),
            ("GNSS Receiver", "FC Connection", "Type"): ("None", *SERIAL_PORTS, *CAN_PORTS),
            ("GNSS Receiver", "FC Connection", "Protocol"): get_combobox_values("GPS_TYPE"),
            ("Battery", "Specifications", "Chemistry"): BatteryCell.chemistries(),
        }
        return combobox_dict.get(path, ())

    def has_validation_rules(self, path: ValidationRulePath) -> bool:
        """Check if validation rules exist for a given path without running validation."""
        return path in self.VALIDATION_RULES

    def validate_entry_limits(self, value: str, path: ValidationRulePath) -> tuple[bool, str]:
        """Validate entry values against limits. Returns (is_valid, error_message)."""
        if not self.has_validation_rules(path):
            return True, ""

        data_type, limits, name = self.VALIDATION_RULES[path]

        try:
            typed_value = data_type(value)
            if typed_value < limits[0] or typed_value > limits[1]:
                error_msg = _("{name} must be a {data_type.__name__} between {limits[0]} and {limits[1]}")
                return False, error_msg.format(name=name, data_type=data_type, limits=limits)
        except ValueError as e:
            return False, str(e)

        return True, ""

    def validate_cell_voltage(self, value: str, path: ValidationRulePath, chemistry: str) -> tuple[bool, str, str]:
        """
        Validate battery cell voltage.

        Returns (is_valid, error_message, corrected_value)
        """
        try:
            voltage = float(value)
            volt_limit = BatteryCell.limit_min_voltage(chemistry)
            if voltage < volt_limit:
                error_msg = _("is below the {chemistry} minimum limit of {volt_limit}")
                return False, error_msg.format(chemistry=chemistry, volt_limit=volt_limit), str(volt_limit)

            volt_limit = BatteryCell.limit_max_voltage(chemistry)
            if voltage > volt_limit:
                error_msg = _("is above the {chemistry} maximum limit of {volt_limit}")
                return False, error_msg.format(chemistry=chemistry, volt_limit=volt_limit), str(volt_limit)

        except ValueError as e:
            # Set to recommended value based on path
            if path[-1] == "Volt per cell max":
                corrected = str(BatteryCell.recommended_max_voltage(chemistry))
            elif path[-1] == "Volt per cell low":
                corrected = str(BatteryCell.recommended_low_voltage(chemistry))
            elif path[-1] == "Volt per cell crit":
                corrected = str(BatteryCell.recommended_crit_voltage(chemistry))
            else:
                corrected = "3.8"

            error_msg = _("Invalid value. Will be set to the recommended value.")
            return False, f"{e!s}\n{error_msg}", corrected

        return True, "", value

    def validate_all_data(self, entry_values: dict[ValidationRulePath, str], doc_dict: dict) -> tuple[bool, list[str]]:  # pylint: disable=too-many-locals,too-many-branches
        """
        Centralize all data validation logic.

        Returns (is_valid, error_messages).
        """
        errors = []
        fc_serial_connection: dict[str, str] = {}

        for path, value in entry_values.items():
            # Validate combobox values
            combobox_values = self.get_combobox_values_for_path(path, doc_dict)
            if combobox_values and value not in combobox_values:
                _paths_str = ">".join(list(path))
                _allowed_str = ", ".join(combobox_values)
                error_msg = _("Invalid value '{value}' for {_paths_str}\nAllowed values are: {_allowed_str}")
                errors.append(error_msg.format(value=value, _paths_str=_paths_str, _allowed_str=_allowed_str))
                continue

            # Check for duplicate connections
            if len(path) >= 3 and path[1] == "FC Connection" and path[2] == "Type":
                if value in fc_serial_connection and value not in {"CAN1", "CAN2", "I2C1", "I2C2", "I2C3", "I2C4", "None"}:
                    battery_monitor_protocol = self.get_component_value(("Battery Monitor", "FC Connection", "Protocol"))

                    # Allow certain combinations
                    if path[0] in {"Telemetry", "RC Receiver"} and fc_serial_connection[value] in {"Telemetry", "RC Receiver"}:
                        continue
                    if (
                        battery_monitor_protocol == "ESC"
                        and path[0] in {"Battery Monitor", "ESC"}
                        and fc_serial_connection[value] in {"Battery Monitor", "ESC"}
                    ):
                        continue

                    _paths_str = ">".join(list(path))
                    error_msg = _("Duplicate FC connection type '{value}' for {_paths_str}")
                    errors.append(error_msg.format(value=value, _paths_str=_paths_str))
                    continue
                fc_serial_connection[value] = path[0]

            # Validate entry limits
            is_valid, error_msg = self.validate_entry_limits(value, path)
            if not is_valid:
                _paths_str = ">".join(list(path))
                errors.append(f"Invalid value '{value}' for {_paths_str}\n{error_msg}")

            # Validate battery cell voltages
            if len(path) >= 3 and path[0] == "Battery" and path[1] == "Specifications":
                if path[2] in {"Volt per cell max", "Volt per cell low", "Volt per cell crit"}:
                    chemistry = entry_values.get(("Battery", "Specifications", "Chemistry"), "Lipo")
                    is_valid, error_msg, _corrected_value = self.validate_cell_voltage(value, path, chemistry)
                    if not is_valid:
                        _path_str = ">".join(list(path))
                        errors.append(f"Invalid value '{value}' for {_path_str}\n{error_msg}")

                # Check voltage relationships
                if path[2] == "Volt per cell low":
                    max_voltage_str = entry_values.get(("Battery", "Specifications", "Volt per cell max"), "0")
                    try:
                        if float(value) >= float(max_voltage_str):
                            errors.append(_("Battery Cell Low voltage must be lower than max voltage"))
                    except ValueError:
                        pass

                if path[2] == "Volt per cell crit":
                    low_voltage_str = entry_values.get(("Battery", "Specifications", "Volt per cell low"), "0")
                    try:
                        if float(value) >= float(low_voltage_str):
                            errors.append(_("Battery Cell Crit voltage must be lower than low voltage"))
                    except ValueError:
                        pass

        return len(errors) == 0, errors
