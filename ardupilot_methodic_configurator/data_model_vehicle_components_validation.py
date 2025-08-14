"""
Data model for vehicle components.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# from logging import debug as logging_debug
import functools
import operator
from logging import error as logging_error
from types import MappingProxyType
from typing import Any, Optional, Union

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents
from ardupilot_methodic_configurator.battery_cell_voltages import BatteryCell
from ardupilot_methodic_configurator.data_model_vehicle_components_base import (
    ComponentData,
    ComponentDataModelBase,
    ComponentPath,
    ComponentValue,
)

# Port definitions
ANALOG_PORTS = ["Analog"]
SERIAL_PORTS = ["SERIAL1", "SERIAL2", "SERIAL3", "SERIAL4", "SERIAL5", "SERIAL6", "SERIAL7", "SERIAL8"]
CAN_PORTS = ["CAN1", "CAN2"]
I2C_PORTS = ["I2C1", "I2C2", "I2C3", "I2C4"]
PWM_IN_PORTS = ["PWM"]
PWM_OUT_PORTS = ["Main Out", "AIO"]
RC_PORTS = ["RCin/SBUS"]
SPI_PORTS = ["SPI"]
OTHER_PORTS = ["other"]

# Map paths to component names for unified protocol update
FC_CONNECTION_TYPE_PATHS: list[ComponentPath] = [
    ("RC Receiver", "FC Connection", "Type"),
    ("Telemetry", "FC Connection", "Type"),
    ("Battery Monitor", "FC Connection", "Type"),
    ("ESC", "FC Connection", "Type"),
    ("GNSS Receiver", "FC Connection", "Type"),
]

BATTERY_CELL_VOLTAGE_PATHS: list[ComponentPath] = [
    ("Battery", "Specifications", "Volt per cell max"),
    ("Battery", "Specifications", "Volt per cell low"),
    ("Battery", "Specifications", "Volt per cell crit"),
]

# Protocol dictionaries
SERIAL_PROTOCOLS_DICT: dict[str, dict[str, Any]] = {
    "-1": {"type": ["None"], "protocol": "None", "component": None},
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

BATT_MONITOR_CONNECTION: dict[str, dict[str, Union[list[str], str]]] = {
    "0": {"type": ["None"], "protocol": "Disabled"},
    "3": {"type": ANALOG_PORTS, "protocol": "Analog Voltage Only"},
    "4": {"type": ANALOG_PORTS, "protocol": "Analog Voltage and Current"},
    "5": {"type": I2C_PORTS, "protocol": "Solo"},
    "6": {"type": I2C_PORTS, "protocol": "Bebop"},
    "7": {"type": I2C_PORTS, "protocol": "SMBus-Generic"},
    "8": {"type": CAN_PORTS, "protocol": "DroneCAN-BatteryInfo"},
    "9": {"type": OTHER_PORTS, "protocol": "ESC"},
    "10": {"type": OTHER_PORTS, "protocol": "Sum Of Selected Monitors"},
    "11": {"type": I2C_PORTS, "protocol": "FuelFlow"},
    "12": {"type": PWM_IN_PORTS, "protocol": "FuelLevelPWM"},
    "13": {"type": I2C_PORTS, "protocol": "SMBUS-SUI3"},
    "14": {"type": I2C_PORTS, "protocol": "SMBUS-SUI6"},
    "15": {"type": I2C_PORTS, "protocol": "NeoDesign"},
    "16": {"type": I2C_PORTS, "protocol": "SMBus-Maxell"},
    "17": {"type": I2C_PORTS, "protocol": "Generator-Elec"},
    "18": {"type": I2C_PORTS, "protocol": "Generator-Fuel"},
    "19": {"type": I2C_PORTS, "protocol": "Rotoye"},
    "20": {"type": I2C_PORTS, "protocol": "MPPT"},
    "21": {"type": I2C_PORTS, "protocol": "INA2XX"},
    "22": {"type": I2C_PORTS, "protocol": "LTC2946"},
    "23": {"type": OTHER_PORTS, "protocol": "Torqeedo"},
    "24": {"type": ANALOG_PORTS, "protocol": "FuelLevelAnalog"},
    "25": {"type": ANALOG_PORTS, "protocol": "Synthetic Current and Analog Voltage"},
    "26": {"type": SPI_PORTS, "protocol": "INA239_SPI"},
    "27": {"type": I2C_PORTS, "protocol": "EFI"},
    "28": {"type": I2C_PORTS, "protocol": "AD7091R5"},
    "29": {"type": OTHER_PORTS, "protocol": "Scripting"},
}

GNSS_RECEIVER_CONNECTION: dict[str, dict[str, Union[list[str], str]]] = {
    "0": {"type": ["None"], "protocol": "None"},
    "1": {"type": SERIAL_PORTS, "protocol": "AUTO"},
    "2": {"type": SERIAL_PORTS, "protocol": "uBlox"},
    "5": {"type": SERIAL_PORTS, "protocol": "NMEA"},
    "6": {"type": SERIAL_PORTS, "protocol": "SiRF"},
    "7": {"type": SERIAL_PORTS, "protocol": "HIL"},
    "8": {"type": SERIAL_PORTS, "protocol": "SwiftNav"},
    "9": {"type": CAN_PORTS, "protocol": "DroneCAN"},
    "10": {"type": SERIAL_PORTS, "protocol": "SBF"},
    "11": {"type": SERIAL_PORTS, "protocol": "GSOF"},
    "13": {"type": SERIAL_PORTS, "protocol": "ERB"},
    "14": {"type": SERIAL_PORTS, "protocol": "MAV"},
    "15": {"type": SERIAL_PORTS, "protocol": "NOVA"},
    "16": {"type": SERIAL_PORTS, "protocol": "HemisphereNMEA"},
    "17": {"type": SERIAL_PORTS, "protocol": "uBlox-MovingBaseline-Base"},
    "18": {"type": SERIAL_PORTS, "protocol": "uBlox-MovingBaseline-Rover"},
    "19": {"type": SERIAL_PORTS, "protocol": "MSP"},
    "20": {"type": SERIAL_PORTS, "protocol": "AllyStar"},
    "21": {"type": SERIAL_PORTS, "protocol": "ExternalAHRS"},
    "22": {"type": CAN_PORTS, "protocol": "DroneCAN-MovingBaseline-Base"},
    "23": {"type": CAN_PORTS, "protocol": "DroneCAN-MovingBaseline-Rover"},
    "24": {"type": SERIAL_PORTS, "protocol": "UnicoreNMEA"},
    "25": {"type": SERIAL_PORTS, "protocol": "UnicoreMovingBaselineNMEA"},
    "26": {"type": SERIAL_PORTS, "protocol": "SBF-DualAntenna"},
}

MOT_PWM_TYPE_DICT: dict[str, dict[str, Union[list[str], str, bool]]] = {
    "0": {"type": PWM_OUT_PORTS, "protocol": "Normal", "is_dshot": False},
    "1": {"type": PWM_OUT_PORTS, "protocol": "OneShot", "is_dshot": True},
    "2": {"type": PWM_OUT_PORTS, "protocol": "OneShot125", "is_dshot": True},
    "3": {"type": PWM_OUT_PORTS, "protocol": "Brushed", "is_dshot": False},
    "4": {"type": PWM_OUT_PORTS, "protocol": "DShot150", "is_dshot": True},
    "5": {"type": PWM_OUT_PORTS, "protocol": "DShot300", "is_dshot": True},
    "6": {"type": PWM_OUT_PORTS, "protocol": "DShot600", "is_dshot": True},
    "7": {"type": PWM_OUT_PORTS, "protocol": "DShot1200", "is_dshot": True},
    "8": {"type": PWM_OUT_PORTS, "protocol": "PWMRange", "is_dshot": False},
}

RC_PROTOCOLS_DICT: dict[str, dict[str, Union[list[str], str]]] = {
    "0": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "All"},
    "1": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "PPM"},
    "2": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "IBUS"},
    "3": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "SBUS"},
    "4": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "SBUS_NI"},
    "5": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "DSM"},
    "6": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "SUMD"},
    "7": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "SRXL"},
    "8": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "SRXL2"},
    "9": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "CRSF"},
    "10": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "ST24"},
    "11": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "FPORT"},
    "12": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "FPORT2"},
    "13": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "FastSBUS"},
    "14": {"type": CAN_PORTS, "protocol": "DroneCAN"},
    "15": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "Ghost"},
}


class ComponentDataModelValidation(ComponentDataModelBase):
    """
    A class to handle component data operations separate from UI logic.

    This improves testability by isolating data operations.
    """

    # Class attribute for validation rules - use immutable mapping
    VALIDATION_RULES: MappingProxyType[ComponentPath, tuple[type, tuple[float, float], str]] = MappingProxyType(
        {
            ("Frame", "Specifications", "TOW min Kg"): (float, (0.01, 600), "Takeoff Weight"),
            ("Frame", "Specifications", "TOW max Kg"): (float, (0.01, 600), "Takeoff Weight"),
            ("Battery", "Specifications", "Number of cells"): (int, (1, 50), "Nr of cells"),
            ("Battery", "Specifications", "Capacity mAh"): (int, (100, 1000000), "mAh capacity"),
            ("Motors", "Specifications", "Poles"): (int, (3, 50), "Motor Poles"),
            ("Propellers", "Specifications", "Diameter_inches"): (float, (0.3, 400), "Propeller Diameter"),
        }
    )

    def set_component_value(self, path: ComponentPath, value: Union[ComponentData, ComponentValue, None]) -> None:
        ComponentDataModelBase.set_component_value(self, path, value)

        # and change side effects
        if path == ("Battery", "Specifications", "Chemistry") and isinstance(value, str) and self._battery_chemistry != value:
            self._battery_chemistry = value
            self.set_component_value(
                ("Battery", "Specifications", "Volt per cell max"), BatteryCell.recommended_max_voltage(value)
            )
            self.set_component_value(
                ("Battery", "Specifications", "Volt per cell low"), BatteryCell.recommended_low_voltage(value)
            )
            self.set_component_value(
                ("Battery", "Specifications", "Volt per cell crit"), BatteryCell.recommended_crit_voltage(value)
            )

        # Update possible choices for protocol fields when connection type changes
        self._update_possible_choices_for_path(path, value)

    def is_valid_component_data(self) -> bool:
        """
        Validate the component data structure.

        Performs basic validation to ensure the data has the expected format.
        """
        return isinstance(self._data, dict) and "Components" in self._data and isinstance(self._data["Components"], dict)

    def init_possible_choices(self, doc_dict: dict) -> None:
        """Get valid combobox values for a given path."""

        # Default values for comboboxes in case the apm.pdef.xml metadata is not available
        def get_all_protocols(param_dict: dict) -> tuple[str, ...]:
            return tuple(
                value["protocol"] if isinstance(value["protocol"], str) else value["protocol"][0]
                for value in param_dict.values()
            )

        fallbacks: dict[str, tuple[str, ...]] = {
            "RC_PROTOCOLS": get_all_protocols(RC_PROTOCOLS_DICT),
            "BATT_MONITOR": get_all_protocols(BATT_MONITOR_CONNECTION),
            "MOT_PWM_TYPE": get_all_protocols(MOT_PWM_TYPE_DICT),
            "GPS_TYPE": get_all_protocols(GNSS_RECEIVER_CONNECTION),
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

        def get_connection_types(conn_dict: dict) -> tuple[str, ...]:
            return tuple(
                dict.fromkeys(  # Use dict.fromkeys to preserve order while removing duplicates
                    functools.reduce(
                        operator.iadd,
                        [
                            type_val if isinstance(type_val, list) else [type_val]
                            for type_val in [value["type"] for value in conn_dict.values()]
                        ],
                        [],
                    )
                )
            )

        if "MOT_PWM_TYPE" in doc_dict:
            self._mot_pwm_types = get_combobox_values("MOT_PWM_TYPE")
        if "Q_M_PWM_TYPE" in doc_dict:
            self._mot_pwm_types = get_combobox_values("Q_M_PWM_TYPE")

        self._possible_choices = {
            ("Flight Controller", "Firmware", "Type"): VehicleComponents.supported_vehicles(),
            ("RC Receiver", "FC Connection", "Type"): get_connection_types(RC_PROTOCOLS_DICT),
            ("RC Receiver", "FC Connection", "Protocol"): get_combobox_values("RC_PROTOCOLS"),
            ("Telemetry", "FC Connection", "Type"): ("None", *SERIAL_PORTS, *CAN_PORTS),
            ("Telemetry", "FC Connection", "Protocol"): tuple(
                value["protocol"] for value in SERIAL_PROTOCOLS_DICT.values() if value["component"] == "Telemetry"
            ),
            ("Battery Monitor", "FC Connection", "Type"): get_connection_types(BATT_MONITOR_CONNECTION),
            ("Battery Monitor", "FC Connection", "Protocol"): get_combobox_values("BATT_MONITOR"),
            ("ESC", "FC Connection", "Type"): (*PWM_OUT_PORTS, *SERIAL_PORTS, *CAN_PORTS),
            ("ESC", "FC Connection", "Protocol"): self._mot_pwm_types,
            ("GNSS Receiver", "FC Connection", "Type"): ("None", *SERIAL_PORTS, *CAN_PORTS),
            ("GNSS Receiver", "FC Connection", "Protocol"): get_combobox_values("GPS_TYPE"),
            ("Battery", "Specifications", "Chemistry"): BatteryCell.chemistries(),
        }
        for component in ["RC Receiver", "Telemetry", "Battery Monitor", "ESC", "GNSS Receiver"]:
            if component in self._data["Components"]:
                self._update_possible_choices_for_path(
                    (component, "FC Connection", "Type"), self.get_component_value((component, "FC Connection", "Type"))
                )

    def _update_possible_choices_for_path(  # pylint: disable=too-many-branches
        self, path: ComponentPath, value: Union[ComponentData, ComponentValue, None]
    ) -> None:
        """Update _possible_choices when connection type values that affect protocol choices are changed."""
        # Only update if this is a connection type change that affects protocol choices
        if len(path) >= 3 and path[1] == "FC Connection" and path[2] == "Type" and isinstance(value, str):
            component_name = path[0]
            protocol_path: ComponentPath = (component_name, "FC Connection", "Protocol")

            # Calculate the new possible choices for the corresponding protocol field
            if component_name == "RC Receiver":
                # Filter RC protocols based on the selected connection type
                if value == "None":
                    new_choices: tuple[str, ...] = ("None",)
                else:
                    # For any connection type, find protocols that support it
                    new_choices = tuple(str(v["protocol"]) for v in RC_PROTOCOLS_DICT.values() if value in v["type"])
                self._possible_choices[protocol_path] = new_choices

            elif component_name == "Telemetry":
                if value == "None":
                    self._possible_choices[protocol_path] = ("None",)
                else:
                    # For non-None telemetry connections, use the standard telemetry protocols
                    self._possible_choices[protocol_path] = tuple(
                        str(v["protocol"]) for v in SERIAL_PROTOCOLS_DICT.values() if v["component"] == "Telemetry"
                    )

            elif component_name == "Battery Monitor":
                if value == "None":
                    self._possible_choices[protocol_path] = ("None",)
                    return

                # Find protocols available for the selected connection type
                batt_available_protocols: list[str] = []
                for conn_dict in BATT_MONITOR_CONNECTION.values():
                    conn_type = conn_dict["type"]
                    # Handle both list and direct port type references
                    if isinstance(conn_type, list):
                        if value in conn_type:
                            batt_available_protocols.append(str(conn_dict["protocol"]))
                    elif value in conn_type:
                        # conn_type is a reference to a port list (e.g., ANALOG_PORTS, I2C_PORTS)
                        batt_available_protocols.append(str(conn_dict["protocol"]))

                self._possible_choices[protocol_path] = (
                    tuple(batt_available_protocols) if batt_available_protocols else ("None",)
                )

            elif component_name == "ESC":
                if value == "None":
                    self._possible_choices[protocol_path] = ("None",)
                elif value in CAN_PORTS:
                    self._possible_choices[protocol_path] = ("DroneCAN",)
                elif value in SERIAL_PORTS:
                    self._possible_choices[protocol_path] = tuple(
                        str(v["protocol"]) for v in SERIAL_PROTOCOLS_DICT.values() if v["component"] == "ESC"
                    )
                else:
                    # For PWM outputs, use motor PWM types
                    self._possible_choices[protocol_path] = self._mot_pwm_types

            elif component_name == "GNSS Receiver":
                if value == "None":
                    self._possible_choices[protocol_path] = ("None",)
                    return

                # Find protocols available for the selected connection type
                gnss_available_protocols: list[str] = []
                for conn_dict in GNSS_RECEIVER_CONNECTION.values():
                    conn_type = conn_dict["type"]
                    # Handle both list and direct port type references
                    if isinstance(conn_type, list):
                        if value in conn_type:
                            gnss_available_protocols.append(str(conn_dict["protocol"]))
                    elif value in conn_type:
                        # conn_type is a reference to a port list (e.g., SERIAL_PORTS, CAN_PORTS)
                        gnss_available_protocols.append(str(conn_dict["protocol"]))

                self._possible_choices[protocol_path] = (
                    tuple(gnss_available_protocols) if gnss_available_protocols else ("None",)
                )

    def validate_entry_limits(self, value: str, path: ComponentPath) -> tuple[str, Optional[float]]:  # noqa: PLR0911 # pylint: disable=too-many-return-statements
        """
        Validate entry values against limits.

        Returns: (error_message, limited_value) if validation fails, or ("", None) if valid.
        """
        if path in self.VALIDATION_RULES:
            data_type, limits, name = self.VALIDATION_RULES[path]
            try:
                typed_value = data_type(value)
                if typed_value < limits[0] or typed_value > limits[1]:
                    error_msg = _("{name} must be a {data_type.__name__} between {limits[0]} and {limits[1]}")
                    limited_value = limits[0] if typed_value < limits[0] else limits[1]
                    return error_msg.format(name=name, data_type=data_type, limits=limits), limited_value
            except ValueError as e:
                return str(e), None

            # Validate takeoff weight limits
            if path[0] == "Frame" and path[1] == "Specifications" and "TOW" in path[2]:
                if path[2] == "TOW max Kg":
                    try:
                        tow_max = float(value)
                    except ValueError:
                        return _("Takeoff Weight max must be a float"), None
                    lim = self.get_component_value(("Frame", "Specifications", "TOW min Kg"))
                    if lim:
                        return self.validate_against_another_value(tow_max, lim, "TOW min Kg", above=True, delta=0.01)

                if path[2] == "TOW min Kg":
                    try:
                        tow_min = float(value)
                    except ValueError:
                        return _("Takeoff Weight min must be a float"), None
                    lim = self.get_component_value(("Frame", "Specifications", "TOW max Kg"))
                    if lim:
                        return self.validate_against_another_value(tow_min, lim, "TOW max Kg", above=False, delta=0.01)

        if path in BATTERY_CELL_VOLTAGE_PATHS:
            return self.validate_cell_voltage(value, path)

        return "", None  # value is within valid interval, return empty string as there is no error

    def validate_cell_voltage(self, value: str, path: ComponentPath) -> tuple[str, Optional[float]]:  # noqa: PLR0911 # pylint: disable=too-many-return-statements
        """
        Validate battery cell voltage.

        Returns (error_message, corrected_value) if validation fails, or ("", None) if valid.
        """
        if path[0] == "Battery" and path[1] == "Specifications" and "Volt per cell" in path[2]:
            recommended_cell_voltage: float = self.recommended_cell_voltage(path)
            try:
                voltage = float(value)
                volt_limit = BatteryCell.limit_min_voltage(self._battery_chemistry)
                if voltage < volt_limit:
                    error_msg = _("is below the {chemistry} minimum limit of {volt_limit}")
                    return error_msg.format(chemistry=self._battery_chemistry, volt_limit=volt_limit), volt_limit

                volt_limit = BatteryCell.limit_max_voltage(self._battery_chemistry)
                if voltage > volt_limit:
                    error_msg = _("is above the {chemistry} maximum limit of {volt_limit}")
                    return error_msg.format(chemistry=self._battery_chemistry, volt_limit=volt_limit), volt_limit

            except ValueError as e:
                error_msg = _("Invalid value. Will be set to the recommended value.")
                return f"{e!s}\n{error_msg}", recommended_cell_voltage

            if path[-1] == "Volt per cell max":
                lim = self.get_component_value(("Battery", "Specifications", "Volt per cell low"))
                return self.validate_against_another_value(voltage, lim, "Volt per cell low", above=True, delta=0.01)

            if path[-1] == "Volt per cell low":
                lim = self.get_component_value(("Battery", "Specifications", "Volt per cell max"))
                err_msg, corr = self.validate_against_another_value(voltage, lim, "Volt per cell max", above=False, delta=0.01)
                if err_msg:
                    return err_msg, corr
                lim = self.get_component_value(("Battery", "Specifications", "Volt per cell crit"))
                return self.validate_against_another_value(voltage, lim, "Volt per cell crit", above=True, delta=0.01)

            if path[-1] == "Volt per cell crit":
                lim = self.get_component_value(("Battery", "Specifications", "Volt per cell low"))
                return self.validate_against_another_value(voltage, lim, "Volt per cell low", above=False, delta=0.01)

        return "", None

    def recommended_cell_voltage(self, path: ComponentPath) -> float:
        """Get recommended cell voltage based on the path."""
        if path[-1] == "Volt per cell max":
            return BatteryCell.recommended_max_voltage(self._battery_chemistry)
        if path[-1] == "Volt per cell low":
            return BatteryCell.recommended_low_voltage(self._battery_chemistry)
        if path[-1] == "Volt per cell crit":
            return BatteryCell.recommended_crit_voltage(self._battery_chemistry)
        return 3.8

    def validate_against_another_value(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        value: float,
        limit_value,  # limit_value has no type, because it can have any type # noqa: ANN001
        limit_name: str,
        above: bool,
        delta: float,
    ) -> tuple[str, Optional[float]]:
        """Validate user defined value against another user defined value."""
        if not isinstance(limit_value, (float, str, int)):
            return _("{limit_name} is not a float nor string").format(limit_name=limit_name), None
        try:
            limit_value = float(limit_value)
        except ValueError:
            return _("{limit_name} is not convertible to float").format(limit_name=limit_name), None
        if above:
            if value < limit_value:
                corrected = limit_value + delta
                return _("is below the {limit_name} of {limit_value}").format(
                    limit_name=limit_name, limit_value=limit_value
                ), corrected
        elif value > limit_value:
            corrected = limit_value - delta
            return _("is above the {limit_name} of {limit_value}").format(
                limit_name=limit_name, limit_value=limit_value
            ), corrected
        return "", None  # value is within valid interval, return empty string as there is no error

    def validate_all_data(self, entry_values: dict[ComponentPath, str]) -> tuple[bool, list[str]]:
        """
        Centralize all data validation logic.

        Returns (is_valid, error_messages).
        """
        errors = []
        fc_serial_connection: dict[str, str] = {}

        for path, value in entry_values.items():
            paths_str = ">".join(list(path))

            # Validate combobox values
            combobox_values = self.get_combobox_values_for_path(path)
            if combobox_values and value not in combobox_values:
                allowed_str = ", ".join(combobox_values)
                error_msg = _("Invalid value '{value}' for {paths_str}\nAllowed values are: {allowed_str}")
                errors.append(error_msg.format(value=value, paths_str=paths_str, allowed_str=allowed_str))
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

                    error_msg = _("Duplicate FC connection type '{value}' for {paths_str}")
                    errors.append(error_msg.format(value=value, paths_str=paths_str))
                    continue
                fc_serial_connection[value] = path[0]

            if path in self.VALIDATION_RULES:
                # Validate entry limits
                error_msg, corrected_value = self.validate_entry_limits(value, path)
                if error_msg:
                    errors.append(error_msg.format(value=value, paths_str=paths_str))
                    if corrected_value is not None:
                        self.set_component_value(path, corrected_value)
                    continue

            if path in BATTERY_CELL_VOLTAGE_PATHS:
                # Validate battery cell voltages
                error_msg, corrected_value = self.validate_cell_voltage(value, path)
                if error_msg:
                    errors.append(error_msg.format(value=value, paths_str=paths_str))
                    if corrected_value is not None:
                        self.set_component_value(path, corrected_value)
                    continue

        return len(errors) == 0, errors
