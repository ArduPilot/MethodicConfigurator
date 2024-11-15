#!/usr/bin/env python3

"""
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import tkinter as tk
from argparse import ArgumentParser
from logging import basicConfig as logging_basicConfig

# from logging import debug as logging_debug
# from logging import info as logging_info
from logging import error as logging_error
from logging import getLevelName as logging_getLevelName
from math import log2
from tkinter import ttk
from typing import Any, Union

from MethodicConfigurator import _, __version__
from MethodicConfigurator.backend_filesystem import LocalFilesystem
from MethodicConfigurator.backend_filesystem_vehicle_components import VehicleComponents
from MethodicConfigurator.battery_cell_voltages import BatteryCell
from MethodicConfigurator.common_arguments import add_common_arguments_and_parse

# from MethodicConfigurator.frontend_tkinter_base import show_tooltip
from MethodicConfigurator.frontend_tkinter_base import show_error_message
from MethodicConfigurator.frontend_tkinter_component_editor_base import ComponentEditorWindowBase


def argument_parser():
    """
    Parses command-line arguments for the script.

    This function sets up an argument parser to handle the command-line arguments for the script.

    Returns:
    argparse.Namespace: An object containing the parsed arguments.
    """
    # pylint: disable=duplicate-code
    parser = ArgumentParser(
        description=_(
            "A GUI for editing JSON files that contain vehicle component configurations. "
            "Not to be used directly, but through the main ArduPilot methodic configurator script."
        )
    )
    parser = LocalFilesystem.add_argparse_arguments(parser)
    parser = ComponentEditorWindow.add_argparse_arguments(parser)
    return add_common_arguments_and_parse(parser)
    # pylint: enable=duplicate-code


class VoltageTooLowError(Exception):
    """Raised when the voltage is below the minimum limit."""


class VoltageTooHighError(Exception):
    """Raised when the voltage is above the maximum limit."""


analog_ports = ["Analog"]
serial_ports = ["SERIAL1", "SERIAL2", "SERIAL3", "SERIAL4", "SERIAL5", "SERIAL6", "SERIAL7", "SERIAL8"]
can_ports = ["CAN1", "CAN2"]
i2c_ports = ["I2C1", "I2C2", "I2C3", "I2C4"]
pwm_ports = ["Main Out", "AIO"]
rc_ports = ["RCin/SBUS"]

serial_protocols_dict: dict[str, dict[str, Any]] = {
    "-1": {"type": serial_ports, "protocol": "None", "component": None},
    "1": {"type": serial_ports, "protocol": "MAVLink1", "component": "Telemetry"},
    "2": {"type": serial_ports, "protocol": "MAVLink2", "component": "Telemetry"},
    "3": {"type": serial_ports, "protocol": "Frsky D", "component": None},
    "4": {"type": serial_ports, "protocol": "Frsky SPort", "component": None},
    "5": {"type": serial_ports, "protocol": "GPS", "component": "GNSS Receiver"},
    "7": {"type": serial_ports, "protocol": "Alexmos Gimbal Serial", "component": None},
    "8": {"type": serial_ports, "protocol": "Gimbal", "component": None},
    "9": {"type": serial_ports, "protocol": "Rangefinder", "component": None},
    "10": {"type": serial_ports, "protocol": "FrSky SPort Passthrough (OpenTX)", "component": None},
    "11": {"type": serial_ports, "protocol": "Lidar360", "component": None},
    "13": {"type": serial_ports, "protocol": "Beacon", "component": None},
    "14": {"type": serial_ports, "protocol": "Volz servo out", "component": None},
    "15": {"type": serial_ports, "protocol": "SBus servo out", "component": None},
    "16": {"type": serial_ports, "protocol": "ESC Telemetry", "component": None},
    "17": {"type": serial_ports, "protocol": "Devo Telemetry", "component": None},
    "18": {"type": serial_ports, "protocol": "OpticalFlow", "component": None},
    "19": {"type": serial_ports, "protocol": "RobotisServo", "component": None},
    "20": {"type": serial_ports, "protocol": "NMEA Output", "component": None},
    "21": {"type": serial_ports, "protocol": "WindVane", "component": None},
    "22": {"type": serial_ports, "protocol": "SLCAN", "component": None},
    "23": {"type": serial_ports, "protocol": "RCIN", "component": "RC Receiver"},
    "24": {"type": serial_ports, "protocol": "EFI Serial", "component": None},
    "25": {"type": serial_ports, "protocol": "LTM", "component": None},
    "26": {"type": serial_ports, "protocol": "RunCam", "component": None},
    "27": {"type": serial_ports, "protocol": "HottTelem", "component": None},
    "28": {"type": serial_ports, "protocol": "Scripting", "component": None},
    "29": {"type": serial_ports, "protocol": "Crossfire VTX", "component": None},
    "30": {"type": serial_ports, "protocol": "Generator", "component": None},
    "31": {"type": serial_ports, "protocol": "Winch", "component": None},
    "32": {"type": serial_ports, "protocol": "MSP", "component": None},
    "33": {"type": serial_ports, "protocol": "DJI FPV", "component": None},
    "34": {"type": serial_ports, "protocol": "AirSpeed", "component": None},
    "35": {"type": serial_ports, "protocol": "ADSB", "component": None},
    "36": {"type": serial_ports, "protocol": "AHRS", "component": None},
    "37": {"type": serial_ports, "protocol": "SmartAudio", "component": None},
    "38": {"type": serial_ports, "protocol": "FETtecOneWire", "component": "ESC"},
    "39": {"type": serial_ports, "protocol": "Torqeedo", "component": "ESC"},
    "40": {"type": serial_ports, "protocol": "AIS", "component": None},
    "41": {"type": serial_ports, "protocol": "CoDevESC", "component": "ESC"},
    "42": {"type": serial_ports, "protocol": "DisplayPort", "component": None},
    "43": {"type": serial_ports, "protocol": "MAVLink High Latency", "component": "Telemetry"},
    "44": {"type": serial_ports, "protocol": "IRC Tramp", "component": None},
    "45": {"type": serial_ports, "protocol": "DDS XRCE", "component": None},
    "46": {"type": serial_ports, "protocol": "IMUDATA", "component": None},
}


batt_monitor_connection: dict[str, dict[str, str]] = {
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


gnss_receiver_connection: dict[str, Any] = {
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

mot_pwm_type_dict: dict[str, dict[str, Any]] = {
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
rc_protocols_dict: dict[str, dict[str, str]] = {
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


class ComponentEditorWindow(ComponentEditorWindowBase):
    """
    This class validates the user input and handles user interactions
    for editing component configurations in the ArduPilot Methodic Configurator.
    """

    def __init__(self, version, local_filesystem: LocalFilesystem):
        self.serial_ports = ["SERIAL1", "SERIAL2", "SERIAL3", "SERIAL4", "SERIAL5", "SERIAL6", "SERIAL7", "SERIAL8"]
        self.can_ports = ["CAN1", "CAN2"]
        self.i2c_ports = ["I2C1", "I2C2", "I2C3", "I2C4"]
        ComponentEditorWindowBase.__init__(self, version, local_filesystem)
        # these are just here so that pygettext extracts them, they have no function
        _vehicle_components_strings = _("Flight Controller")
        _vehicle_components_strings = _("Product")
        _vehicle_components_strings = _("Manufacturer")
        _vehicle_components_strings = _("Model")
        _vehicle_components_strings = _("URL")
        _vehicle_components_strings = _("Version")
        _vehicle_components_strings = _("Firmware")
        _vehicle_components_strings = _("Type")
        _vehicle_components_strings = _("Notes")
        _vehicle_components_strings = _("Frame")
        _vehicle_components_strings = _("Specifications")
        _vehicle_components_strings = _("TOW min Kg")
        _vehicle_components_strings = _("TOW max Kg")
        _vehicle_components_strings = _("RC Controller")
        _vehicle_components_strings = _("RC Transmitter")
        _vehicle_components_strings = _("RC Receiver")
        _vehicle_components_strings = _("FC Connection")
        _vehicle_components_strings = _("Protocol")
        _vehicle_components_strings = _("Telemetry")
        _vehicle_components_strings = _("Battery Monitor")
        _vehicle_components_strings = _("Battery")
        _vehicle_components_strings = _("Chemistry")
        _vehicle_components_strings = _("Volt per cell max")
        _vehicle_components_strings = _("Volt per cell low")
        _vehicle_components_strings = _("Volt per cell crit")
        _vehicle_components_strings = _("Number of cells")
        _vehicle_components_strings = _("Capacity mAh")
        _vehicle_components_strings = _("ESC")
        _vehicle_components_strings = _("Motors")
        _vehicle_components_strings = _("Poles")
        _vehicle_components_strings = _("Propellers")
        _vehicle_components_strings = _("Diameter_inches")
        _vehicle_components_strings = _("GNSS Receiver")

    def update_json_data(self):
        super().update_json_data()
        # To update old JSON files that do not have these new fields
        if "Components" not in self.data:
            self.data["Components"] = {}
        if "Battery" not in self.data["Components"]:
            self.data["Components"]["Battery"] = {}
        if "Specifications" not in self.data["Components"]["Battery"]:
            self.data["Components"]["Battery"]["Specifications"] = {}
        if "Chemistry" not in self.data["Components"]["Battery"]["Specifications"]:
            self.data["Components"]["Battery"]["Specifications"]["Chemistry"] = "Lipo"
        if "Capacity mAh" not in self.data["Components"]["Battery"]["Specifications"]:
            self.data["Components"]["Battery"]["Specifications"]["Capacity mAh"] = 0

        # To update old JSON files that do not have these new fields
        if "Frame" not in self.data["Components"]:
            self.data["Components"]["Frame"] = {}
        if "Specifications" not in self.data["Components"]["Frame"]:
            self.data["Components"]["Frame"]["Specifications"] = {}
        if "TOW min Kg" not in self.data["Components"]["Frame"]["Specifications"]:
            self.data["Components"]["Frame"]["Specifications"]["TOW min Kg"] = 1
        if "TOW max Kg" not in self.data["Components"]["Frame"]["Specifications"]:
            self.data["Components"]["Frame"]["Specifications"]["TOW max Kg"] = 1

        # Older versions used receiver instead of Receiver, rename it for consistency with other fields
        if "GNSS receiver" in self.data["Components"]:
            self.data["Components"]["GNSS Receiver"] = self.data["Components"].pop("GNSS receiver")

        self.data["Program version"] = __version__

    def set_vehicle_type_and_version(self, vehicle_type: str, version: str):
        self._set_component_value_and_update_ui(("Flight Controller", "Firmware", "Type"), vehicle_type)
        if version:
            self._set_component_value_and_update_ui(("Flight Controller", "Firmware", "Version"), version)

    def set_fc_manufacturer(self, manufacturer: str):
        if manufacturer and manufacturer not in ("Unknown", "ArduPilot"):
            self._set_component_value_and_update_ui(("Flight Controller", "Product", "Manufacturer"), manufacturer)

    def set_fc_model(self, model: str):
        if model and model not in ("Unknown", "MAVLink"):
            self._set_component_value_and_update_ui(("Flight Controller", "Product", "Model"), model)

    def set_vehicle_configuration_template(self, configuration_template: str):
        self.data["Configuration template"] = configuration_template

    @staticmethod
    def reverse_key_search(doc: dict, param_name: str, values: list, fallbacks: list) -> list:
        retv = [int(key) for key, value in doc[param_name]["values"].items() if value in values]
        if len(values) != len(fallbacks):
            logging_error(_("Length of values %u and fallbacks %u differ for %s"), len(values), len(fallbacks), param_name)
        if retv:
            return retv
        logging_error(_("No values found for %s in the metadata"), param_name)
        return fallbacks

    def __assert_dict_is_uptodate(self, doc: dict, dict_to_check: dict, doc_key: str, doc_dict: str):
        """Asserts that the given dictionary is up-to-date with the apm.pdef.xml documentation metadata."""
        if doc and doc_key in doc and doc[doc_key] and doc_dict in doc[doc_key]:
            for key, doc_protocol in doc[doc_key][doc_dict].items():
                if key in dict_to_check:
                    code_protocol = dict_to_check[key].get("protocol", None)
                    if code_protocol != doc_protocol:
                        logging_error(_("Protocol %s does not match %s in %s metadata"), code_protocol, doc_protocol, doc_key)
                else:
                    logging_error(_("Protocol %s not found in %s metadata"), doc_protocol, doc_key)

    def set_values_from_fc_parameters(self, fc_parameters: dict, doc: dict):
        self.__assert_dict_is_uptodate(doc, serial_protocols_dict, "SERIAL1_PROTOCOL", "values")
        self.__assert_dict_is_uptodate(doc, batt_monitor_connection, "BATT_MONITOR", "values")
        self.__assert_dict_is_uptodate(doc, gnss_receiver_connection, "GPS_TYPE", "values")
        self.__assert_dict_is_uptodate(doc, mot_pwm_type_dict, "MOT_PWM_TYPE", "values")
        self.__assert_dict_is_uptodate(doc, rc_protocols_dict, "RC_PROTOCOLS", "Bitmask")

        self.__set_gnss_type_and_protocol_from_fc_parameters(fc_parameters)
        esc_is_serial_controlled = self.__set_serial_type_and_protocol_from_fc_parameters(fc_parameters)
        if not esc_is_serial_controlled:
            self.__set_esc_type_and_protocol_from_fc_parameters(fc_parameters, doc)
        self.__set_battery_type_and_protocol_from_fc_parameters(fc_parameters)
        self.__set_motor_poles_from_fc_parameters(fc_parameters)

    def __set_gnss_type_and_protocol_from_fc_parameters(self, fc_parameters: dict):
        gps1_type = fc_parameters.get("GPS_TYPE", 0)
        try:
            gps1_type = int(gps1_type)
        except ValueError:
            logging_error(_("Invalid non-integer value for GPS_TYPE %f"), gps1_type)
            gps1_type = 0
        if str(gps1_type) in gnss_receiver_connection:
            gps1_connection_type = gnss_receiver_connection[str(gps1_type)].get("type")
            gps1_connection_protocol = gnss_receiver_connection[str(gps1_type)].get("protocol")
            if gps1_connection_type is None:
                self.data["Components"]["GNSS Receiver"]["FC Connection"]["Type"] = "None"
                self.data["Components"]["GNSS Receiver"]["FC Connection"]["Protocol"] = "None"
            elif gps1_connection_type == "serial":
                # GNSS connection type will be detected later in set_protocol_and_connection_from_fc_parameters()
                self.data["Components"]["GNSS Receiver"]["FC Connection"]["Protocol"] = gps1_connection_protocol
            elif gps1_connection_type == "can":
                if (
                    "CAN_D1_PROTOCOL" in fc_parameters
                    and fc_parameters["CAN_D1_PROTOCOL"] == 1
                    and "CAN_P1_DRIVER" in fc_parameters
                    and fc_parameters["CAN_P1_DRIVER"] == 1
                ):
                    self.data["Components"]["GNSS Receiver"]["FC Connection"]["Type"] = "CAN1"
                elif (
                    "CAN_D2_PROTOCOL" in fc_parameters
                    and fc_parameters["CAN_D2_PROTOCOL"] == 1
                    and "CAN_P2_DRIVER" in fc_parameters
                    and fc_parameters["CAN_P2_DRIVER"] == 2
                ):
                    self.data["Components"]["GNSS Receiver"]["FC Connection"]["Type"] = "CAN2"
                else:
                    logging_error(
                        _("Invalid CAN_Dx_PROTOCOL %s and CAN_Px_DRIVER %s for GNSS Receiver"),
                        fc_parameters.get("CAN_D1_PROTOCOL"),
                        fc_parameters.get("CAN_P1_DRIVER"),
                    )
                    self.data["Components"]["GNSS Receiver"]["FC Connection"]["Type"] = "None"
                self.data["Components"]["GNSS Receiver"]["FC Connection"]["Protocol"] = gps1_connection_protocol
            else:
                logging_error("Invalid GNSS connection type %s", gps1_connection_type)
                self.data["Components"]["GNSS Receiver"]["FC Connection"]["Type"] = "None"
        else:
            logging_error("GPS_TYPE %u not in gnss_receiver_connection", gps1_type)
            self.data["Components"]["GNSS Receiver"]["FC Connection"]["Type"] = "None"

    def __set_serial_type_and_protocol_from_fc_parameters(self, fc_parameters: dict):
        if "RC_PROTOCOLS" in fc_parameters:
            rc_protocols_nr = int(fc_parameters["RC_PROTOCOLS"])
            # check if rc_protocols_nr is a power of two (only one bit set)
            if rc_protocols_nr & (rc_protocols_nr - 1) == 0:
                # rc_bit is the number of the bit that is set
                rc_bit = str(int(log2(rc_protocols_nr)))
                protocol = rc_protocols_dict[rc_bit].get("protocol")
                self.data["Components"]["RC Receiver"]["FC Connection"]["Protocol"] = protocol

        rc = 1
        telem = 1
        gnss = 1
        esc = 1
        for serial in self.serial_ports:
            if serial + "_PROTOCOL" not in fc_parameters:
                continue
            serial_protocol_nr = fc_parameters[serial + "_PROTOCOL"]
            try:
                serial_protocol_nr = int(serial_protocol_nr)
            except ValueError:
                msg = _("Invalid non-integer value for {serial}_PROTOCOL {serial_protocol_nr}")
                logging_error(msg.format(**locals()))
                serial_protocol_nr = 0
            component = serial_protocols_dict[str(serial_protocol_nr)].get("component")
            protocol = serial_protocols_dict[str(serial_protocol_nr)].get("protocol")
            if component is None:
                continue
            if component == "RC Receiver" and rc == 1:
                self.data["Components"][component]["FC Connection"]["Type"] = serial  # only one RC supported
                rc += 1
            elif component == "Telemetry" and telem == 1:
                self.data["Components"][component]["FC Connection"]["Type"] = serial  # only one telemetry supported
                self.data["Components"][component]["FC Connection"]["Protocol"] = protocol
                telem += 1
            elif component == "GNSS Receiver" and gnss == 1:
                self.data["Components"][component]["FC Connection"]["Type"] = serial  # only one GNSS supported
                gnss += 1
            elif component == "ESC" and esc == 1:
                self.data["Components"][component]["FC Connection"]["Type"] = serial  # only one ESC supported
                self.data["Components"][component]["FC Connection"]["Protocol"] = protocol
                esc += 1

        return esc >= 2

    def __set_esc_type_and_protocol_from_fc_parameters(self, fc_parameters: dict, doc: dict):
        mot_pwm_type = fc_parameters.get("MOT_PWM_TYPE", 0)
        try:
            mot_pwm_type = int(mot_pwm_type)
        except ValueError:
            logging_error(_("Invalid non-integer value for MOT_PWM_TYPE %f"), mot_pwm_type)
            mot_pwm_type = 0
        main_out_functions = [fc_parameters.get("SERVO" + str(i) + "_FUNCTION", 0) for i in range(1, 9)]

        # if any element of main_out_functions is in [33, 34, 35, 36] then ESC is connected to main_out
        if any(servo_function in {33, 34, 35, 36} for servo_function in main_out_functions):
            self.data["Components"]["ESC"]["FC Connection"]["Type"] = "Main Out"
        else:
            self.data["Components"]["ESC"]["FC Connection"]["Type"] = "AIO"
        self.data["Components"]["ESC"]["FC Connection"]["Protocol"] = doc["MOT_PWM_TYPE"]["values"][str(mot_pwm_type)]

    def __set_battery_type_and_protocol_from_fc_parameters(self, fc_parameters: dict):
        if "BATT_MONITOR" in fc_parameters:
            batt_monitor = int(fc_parameters["BATT_MONITOR"])
            self.data["Components"]["Battery Monitor"]["FC Connection"]["Type"] = batt_monitor_connection[
                str(batt_monitor)
            ].get("type")
            self.data["Components"]["Battery Monitor"]["FC Connection"]["Protocol"] = batt_monitor_connection[
                str(batt_monitor)
            ].get("protocol")

    def __set_motor_poles_from_fc_parameters(self, fc_parameters: dict):
        if "MOT_PWM_TYPE" in fc_parameters:
            mot_pwm_type_str = str(fc_parameters["MOT_PWM_TYPE"])
            if mot_pwm_type_str in mot_pwm_type_dict and mot_pwm_type_dict[mot_pwm_type_str].get("is_dshot", False):
                if "SERVO_BLH_POLES" in fc_parameters:
                    self.data["Components"]["Motors"]["Specifications"]["Poles"] = fc_parameters["SERVO_BLH_POLES"]
            elif "SERVO_FTW_MASK" in fc_parameters and fc_parameters["SERVO_FTW_MASK"] and "SERVO_FTW_POLES" in fc_parameters:
                self.data["Components"]["Motors"]["Specifications"]["Poles"] = fc_parameters["SERVO_FTW_POLES"]

    def update_esc_protocol_combobox_entries(self, esc_connection_type: str):
        """Updates the ESC Protocol combobox entries based on the selected ESC Type."""
        if len(esc_connection_type) > 3 and esc_connection_type[:3] == "CAN":
            protocols = ["DroneCAN"]
        elif len(esc_connection_type) > 6 and esc_connection_type[:6] == "SERIAL":
            protocols = [value["protocol"] for value in serial_protocols_dict.values() if value["component"] == "ESC"]
        elif "MOT_PWM_TYPE" in self.local_filesystem.doc_dict:
            protocols = list(self.local_filesystem.doc_dict["MOT_PWM_TYPE"]["values"].values())
        elif "Q_M_PWM_TYPE" in self.local_filesystem.doc_dict:
            protocols = list(self.local_filesystem.doc_dict["Q_M_PWM_TYPE"]["values"].values())
        else:
            protocols = []

        protocol_path = ("ESC", "FC Connection", "Protocol")
        if protocol_path in self.entry_widgets:
            protocol_combobox = self.entry_widgets[protocol_path]
            protocol_combobox["values"] = protocols  # Update the combobox entries
            if protocol_combobox.get() not in protocols and isinstance(protocol_combobox, ttk.Combobox):
                protocol_combobox.set(protocols[0] if protocols else "")
            protocol_combobox.update_idletasks()  # re-draw the combobox ASAP

    def add_entry_or_combobox(self, value, entry_frame, path: tuple[str, str, str]) -> Union[ttk.Entry, ttk.Combobox]:
        # Default values for comboboxes in case the apm.pdef.xml metadata is not available
        fallbacks = {
            "RC_PROTOCOLS": [value["protocol"] for value in rc_protocols_dict.values()],
            "BATT_MONITOR": [value["protocol"] for value in batt_monitor_connection.values()],
            "MOT_PWM_TYPE": [value["protocol"] for value in mot_pwm_type_dict.values()],
            "GPS_TYPE": [value["protocol"] for value in gnss_receiver_connection.values()],
        }

        def get_combobox_values(param_name: str) -> list:
            param_metadata = self.local_filesystem.doc_dict
            if param_name in param_metadata:
                if "values" in param_metadata[param_name] and param_metadata[param_name]["values"]:
                    return list(param_metadata[param_name]["values"].values())
                if "Bitmask" in param_metadata[param_name] and param_metadata[param_name]["Bitmask"]:
                    return list(param_metadata[param_name]["Bitmask"].values())
                logging_error(_("No values found for %s in the metadata"), param_name)
            if param_name in fallbacks:
                return fallbacks[param_name]
            logging_error(_("No fallback values found for %s"), param_name)
            return []

        combobox_config = {
            ("Flight Controller", "Firmware", "Type"): {
                "values": VehicleComponents.supported_vehicles(),
            },
            ("RC Receiver", "FC Connection", "Type"): {
                "values": ["RCin/SBUS", *self.serial_ports, *self.can_ports],
            },
            ("RC Receiver", "FC Connection", "Protocol"): {
                "values": get_combobox_values("RC_PROTOCOLS"),
            },
            ("Telemetry", "FC Connection", "Type"): {
                "values": self.serial_ports + self.can_ports,
            },
            ("Telemetry", "FC Connection", "Protocol"): {
                "values": ["MAVLink1", "MAVLink2", "MAVLink High Latency"],
            },
            ("Battery Monitor", "FC Connection", "Type"): {
                "values": ["None", "Analog", "SPI", "PWM", *self.i2c_ports, *self.serial_ports, *self.can_ports],
            },
            ("Battery Monitor", "FC Connection", "Protocol"): {
                "values": get_combobox_values("BATT_MONITOR"),
            },
            ("ESC", "FC Connection", "Type"): {
                "values": ["Main Out", "AIO", *self.serial_ports, *self.can_ports],
            },
            ("ESC", "FC Connection", "Protocol"): {"values": get_combobox_values("MOT_PWM_TYPE")},
            ("GNSS Receiver", "FC Connection", "Type"): {
                "values": ["None", *self.serial_ports, *self.can_ports],
            },
            ("GNSS Receiver", "FC Connection", "Protocol"): {
                "values": get_combobox_values("GPS_TYPE"),
            },
            ("Battery", "Specifications", "Chemistry"): {
                "values": BatteryCell.chemistries(),
            },
        }
        config = combobox_config.get(path)
        if config:
            cb = ttk.Combobox(entry_frame, values=config["values"])
            cb.bind("<FocusOut>", lambda event, path=path: self.validate_combobox(event, path))  # type: ignore
            cb.bind("<KeyRelease>", lambda event, path=path: self.validate_combobox(event, path))  # type: ignore

            if path == ("ESC", "FC Connection", "Type"):  # immediate update of ESC Protocol upon ESC Type selection
                cb.bind(
                    "<<ComboboxSelected>>",
                    lambda event, path=path: self.update_esc_protocol_combobox_entries(cb.get()),  # type: ignore[misc]
                )

            cb.set(value)
            return cb

        entry = ttk.Entry(entry_frame)
        validate_function = self.get_validate_function(entry, path)
        if validate_function:
            entry.bind("<FocusOut>", validate_function)
            entry.bind("<KeyRelease>", validate_function)
        entry.insert(0, str(value))
        return entry

    def get_validate_function(self, entry, path):
        validate_functions = {
            ("Frame", "Specifications", "TOW min Kg"): lambda event, entry=entry, path=path: self.validate_entry_limits(
                event, entry, float, (0.01, 600), "Takeoff Weight", path
            ),
            ("Frame", "Specifications", "TOW max Kg"): lambda event, entry=entry, path=path: self.validate_entry_limits(
                event, entry, float, (0.01, 600), "Takeoff Weight", path
            ),
            ("Battery", "Specifications", "Volt per cell max"): lambda event,
            entry=entry,
            path=path: self.validate_cell_voltage(event, entry, path),
            ("Battery", "Specifications", "Volt per cell low"): lambda event,
            entry=entry,
            path=path: self.validate_cell_voltage(event, entry, path),
            ("Battery", "Specifications", "Volt per cell crit"): lambda event,
            entry=entry,
            path=path: self.validate_cell_voltage(event, entry, path),
            ("Battery", "Specifications", "Number of cells"): lambda event, entry=entry, path=path: self.validate_entry_limits(
                event, entry, int, (1, 50), "Nr of cells", path
            ),
            ("Battery", "Specifications", "Capacity mAh"): lambda event, entry=entry, path=path: self.validate_entry_limits(
                event, entry, int, (100, 1000000), "mAh capacity", path
            ),
            ("Motors", "Specifications", "Poles"): lambda event, entry=entry, path=path: self.validate_entry_limits(
                event, entry, int, (3, 50), "Motor Poles", path
            ),
            ("Propellers", "Specifications", "Diameter_inches"): lambda event,
            entry=entry,
            path=path: self.validate_entry_limits(event, entry, float, (0.3, 400), "Propeller Diameter", path),
        }
        return validate_functions.get(path)

    def validate_combobox(self, event: tk.Event, path: tuple[str, ...]) -> bool:
        """
        Validates the value of a combobox.
        """
        combobox = event.widget  # Get the combobox widget that triggered the event
        value = combobox.get()  # Get the current value of the combobox
        allowed_values = combobox.cget("values")  # Get the list of allowed values

        if value not in allowed_values:
            if event.type == "10":  # FocusOut events
                _paths_str = ">".join(list(path))
                _allowed_str = ", ".join(allowed_values)
                error_msg = _("Invalid value '{value}' for {_paths_str}\nAllowed values are: {_allowed_str}")
                show_error_message(_("Error"), error_msg.format(**locals()))
            combobox.configure(style="comb_input_invalid.TCombobox")
            return False

        if path == ("ESC", "FC Connection", "Type"):
            self.update_esc_protocol_combobox_entries(value)

        combobox.configure(style="comb_input_valid.TCombobox")
        return True

    def validate_entry_limits(self, event, entry, data_type, limits, _name, path):  # pylint: disable=too-many-arguments
        is_focusout_event = event and event.type == "10"
        try:
            value = entry.get()  # make sure value is defined to prevent exception in the except block
            value = data_type(value)
            if value < limits[0] or value > limits[1]:
                entry.configure(style="entry_input_invalid.TEntry")
                error_msg = _("{_name} must be a {data_type.__name__} between {limits[0]} and {limits[1]}")
                raise ValueError(error_msg.format(**locals()))
        except ValueError as _e:
            if is_focusout_event:
                _paths_str = ">".join(list(path))
                error_msg = _("Invalid value '{value}' for {_paths_str}\n{e}")
                show_error_message(_("Error"), error_msg.format(**locals()))
            return False
        entry.configure(style="entry_input_valid.TEntry")
        return True

    def validate_cell_voltage(self, event, entry, path):  # pylint: disable=too-many-branches
        """
        Validates the value of a battery cell voltage entry.
        """
        chemistry_path = ("Battery", "Specifications", "Chemistry")
        if chemistry_path not in self.entry_widgets:
            show_error_message(_("Error"), _("Battery Chemistry not set. Will default to Lipo."))
            chemistry = "Lipo"
        else:
            chemistry = self.entry_widgets[chemistry_path].get()
        value = entry.get()
        is_focusout_event = event and event.type == "10"
        _path_str = ">".join(list(path))
        try:
            voltage = float(value)
            volt_limit = BatteryCell.limit_min_voltage(chemistry)
            if voltage < volt_limit:
                if is_focusout_event:
                    entry.delete(0, tk.END)
                    entry.insert(0, volt_limit)
                error_msg = _("is below the {chemistry} minimum limit of {volt_limit}")
                raise VoltageTooLowError(error_msg.format(**locals()))
            volt_limit = BatteryCell.limit_max_voltage(chemistry)
            if voltage > volt_limit:
                if is_focusout_event:
                    entry.delete(0, tk.END)
                    entry.insert(0, volt_limit)
                error_msg = _("is above the {chemistry} maximum limit of {volt_limit}")
                raise VoltageTooHighError(error_msg.format(**locals()))
        except (VoltageTooLowError, VoltageTooHighError) as _e:
            if is_focusout_event:
                error_msg = _("Invalid value '{value}' for {_path_str}\n{_e}")
                show_error_message(_("Error"), error_msg.format(**locals()))
            else:
                entry.configure(style="entry_input_invalid.TEntry")
                return False
        except ValueError as _e:
            if is_focusout_event:
                error_msg = _("Invalid value '{value}' for {_path_str}\n{_e}\nWill be set to the recommended value.")
                show_error_message(_("Error"), error_msg.format(**locals()))
                entry.delete(0, tk.END)
                if path[-1] == "Volt per cell max":
                    entry.insert(0, str(BatteryCell.recommended_max_voltage(chemistry)))
                elif path[-1] == "Volt per cell low":
                    entry.insert(0, str(BatteryCell.recommended_low_voltage(chemistry)))
                elif path[-1] == "Volt per cell crit":
                    entry.insert(0, str(BatteryCell.recommended_crit_voltage(chemistry)))
                else:
                    entry.insert(0, "3.8")
            else:
                entry.configure(style="entry_input_invalid.TEntry")
                return False
        entry.configure(style="entry_input_valid.TEntry")
        return True

    def save_data(self):
        if self.validate_data():
            ComponentEditorWindowBase.save_data(self)

    def validate_data(self):  # pylint: disable=too-many-branches
        invalid_values = False
        duplicated_connections = False
        fc_serial_connection: dict[str, str] = {}

        for path, entry in self.entry_widgets.items():
            value = entry.get()

            _path_str = ">".join(list(path))
            if isinstance(entry, ttk.Combobox):
                if path == ("ESC", "FC Connection", "Type"):
                    self.update_esc_protocol_combobox_entries(value)
                if value not in entry.cget("values"):
                    _values_str = ", ".join(entry.cget("values"))
                    error_msg = _("Invalid value '{value}' for {_path_str}\nAllowed values are: {_values_str}")
                    show_error_message(_("Error"), error_msg.format(**locals()))
                    entry.configure(style="comb_input_invalid.TCombobox")
                    invalid_values = True
                    continue
                if "FC Connection" in path and "Type" in path:
                    if value in fc_serial_connection and value not in {"CAN1", "CAN2", "I2C1", "I2C2", "I2C3", "I2C4"}:
                        if path[0] in {"Telemetry", "RC Receiver"} and fc_serial_connection[value] in {
                            "Telemetry",
                            "RC Receiver",
                        }:
                            entry.configure(style="comb_input_valid.TCombobox")
                            continue  # Allow telemetry and RC Receiver connections using the same SERIAL port
                        if (
                            self.data["Components"]["Battery Monitor"]["FC Connection"]["Protocol"] == "ESC"
                            and path[0] in {"Battery Monitor", "ESC"}
                            and fc_serial_connection[value] in {"Battery Monitor", "ESC"}
                        ):
                            entry.configure(style="comb_input_valid.TCombobox")
                            continue  # Allow 'Battery Monitor' and 'ESC' connections using the same SERIAL port
                        error_msg = _("Duplicate FC connection type '{value}' for {_path_str}")
                        show_error_message(_("Error"), error_msg.format(**locals()))
                        entry.configure(style="comb_input_invalid.TCombobox")
                        duplicated_connections = True
                        continue
                    fc_serial_connection[value] = path[0]
                entry.configure(style="comb_input_valid.TCombobox")

            validate_function = self.get_validate_function(entry, path)
            if validate_function:
                mock_focus_out_event = type("", (), {"type": "10"})()
                if not validate_function(mock_focus_out_event):
                    invalid_values = True
            if path in {
                ("Battery", "Specifications", "Volt per cell max"),
                ("Battery", "Specifications", "Volt per cell low"),
                ("Battery", "Specifications", "Volt per cell crit"),
            } and not self.validate_cell_voltage(None, entry, path):
                invalid_values = True
            if (
                path == ("Battery", "Specifications", "Volt per cell low")
                and value >= self.entry_widgets[("Battery", "Specifications", "Volt per cell max")].get()
            ):
                show_error_message(_("Error"), _("Battery Cell Low voltage must be lower than max voltage"))
                entry.configure(style="entry_input_invalid.TEntry")
                invalid_values = True
            if (
                path == ("Battery", "Specifications", "Volt per cell crit")
                and value >= self.entry_widgets[("Battery", "Specifications", "Volt per cell low")].get()
            ):
                show_error_message(_("Error"), _("Battery Cell Crit voltage must be lower than low voltage"))
                entry.configure(style="entry_input_invalid.TEntry")
                invalid_values = True

        return not (invalid_values or duplicated_connections)


if __name__ == "__main__":
    args = argument_parser()

    logging_basicConfig(level=logging_getLevelName(args.loglevel), format="%(asctime)s - %(levelname)s - %(message)s")

    filesystem = LocalFilesystem(args.vehicle_dir, args.vehicle_type, "", args.allow_editing_template_files)
    app = ComponentEditorWindow(__version__, filesystem)
    app.root.mainloop()
