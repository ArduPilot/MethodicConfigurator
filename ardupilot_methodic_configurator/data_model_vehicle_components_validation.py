"""
Data model for vehicle components.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

# from logging import debug as logging_debug
import functools
import operator
from logging import error as logging_error
from types import MappingProxyType
from typing import Any, Optional, Union, cast

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_filesystem_vehicle_components import VehicleComponents
from ardupilot_methodic_configurator.battery_cell_voltages import BATTERY_CELL_VOLTAGE_TYPES, BatteryCell
from ardupilot_methodic_configurator.data_model_vehicle_components_base import (
    ComponentData,
    ComponentDataModelBase,
    ComponentPath,
    ComponentValue,
)

# pylint: disable=too-many-lines

# Port definitions
ANALOG_PORTS: tuple[str, ...] = ("Analog",)
SERIAL_PORTS: tuple[str, ...] = ("SERIAL1", "SERIAL2", "SERIAL3", "SERIAL4", "SERIAL5", "SERIAL6", "SERIAL7", "SERIAL8")
CAN_PORTS: tuple[str, ...] = ("CAN1", "CAN2")
I2C_PORTS: tuple[str, ...] = ("I2C1", "I2C2", "I2C3", "I2C4")
PWM_IN_PORTS: tuple[str, ...] = ("PWM",)
PWM_OUT_PORTS: tuple[str, ...] = ("Main Out", "AIO")
RC_PORTS: tuple[str, ...] = ("RCin/SBUS",)
SPI_PORTS: tuple[str, ...] = ("SPI",)
OTHER_PORTS: tuple[str, ...] = ("other",)

# Servo function constants for ESC detection
SERVO_FUNCTION_ESC_CONTROL: set[int] = {33, 34, 35, 36, 73, 74}  # Functions that indicate ESC control on AIO

# Bus labels for SERIAL ports - maps SERIAL port names to their common bus labels
# These labels help users identify ports by their typical usage on flight controllers:
# - Telem1/Telem2: Commonly used for telemetry connections
# - GPS1/GPS2: Commonly used for GNSS receiver connections
# - SERIAL5-8: No standard labels, use port name as label
SERIAL_BUS_LABELS: dict[str, str] = {
    "SERIAL1": "Telem1 (SERIAL1)",
    "SERIAL2": "Telem2 (SERIAL2)",
    "SERIAL3": "GPS1 (SERIAL3)",
    "SERIAL4": "GPS2 (SERIAL4)",
    "SERIAL5": "SERIAL5",
    "SERIAL6": "SERIAL6",
    "SERIAL7": "SERIAL7",
    "SERIAL8": "SERIAL8",
}

# Reverse mapping for efficient lookup: display label -> key (e.g., "GPS1 (SERIAL3)" -> "SERIAL3")
SERIAL_DISPLAY_TO_KEY: dict[str, str] = {display: key for key, display in SERIAL_BUS_LABELS.items()}


def get_connection_type_tuples_with_labels(connection_types: tuple[str, ...]) -> list[tuple[str, str]]:
    """
    Convert connection type values to tuples with bus labels for display.

    Args:
        connection_types: Tuple of connection type values (e.g., ("SERIAL1", "SERIAL2", ...))

    Returns:
        List of tuples where first element is the value and second is the display string.
        For SERIAL ports, returns (value, "Label (value)"), e.g., ("SERIAL3", "GPS1 (SERIAL3)")
        For other ports, returns (value, value), e.g., ("CAN1", "CAN1")

    """
    result = []
    for conn_type in connection_types:
        if conn_type in SERIAL_BUS_LABELS:
            label = SERIAL_BUS_LABELS[conn_type]
            result.append((conn_type, label))
        else:
            result.append((conn_type, conn_type))
    return result


# Map paths to component names for unified protocol update
FC_CONNECTION_TYPE_PATHS: list[ComponentPath] = [
    ("RC Receiver", "FC Connection", "Type"),
    ("Telemetry", "FC Connection", "Type"),
    ("Battery Monitor", "FC Connection", "Type"),
    ("ESC", "FC->ESC Connection", "Type"),
    ("ESC", "ESC->FC Telemetry", "Type"),
    ("GNSS Receiver", "FC Connection", "Type"),
]

BATTERY_CELL_VOLTAGE_PATHS: list[ComponentPath] = [
    ("Battery", "Specifications", voltage_type) for voltage_type in BATTERY_CELL_VOLTAGE_TYPES
]

# Protocol dictionaries
SERIAL_PROTOCOLS_DICT: dict[str, dict[str, Any]] = {
    "-1": {"type": ("None",), "protocol": "None", "component": None},
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
    "16": {"type": SERIAL_PORTS, "protocol": "ESC Telemetry", "component": "ESC"},
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
    "28": {"type": SERIAL_PORTS, "protocol": "Scripting", "component": "ESC"},
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
    "48": {"type": SERIAL_PORTS, "protocol": "PPP", "component": "Telemetry"},
    "49": {"type": SERIAL_PORTS, "protocol": "i-BUS Telemetry", "component": None},
}

# Serial telemetry-only protocols
ESC_TELEMETRY_ONLY_PROTOCOLS: frozenset[str] = frozenset({"ESC Telemetry", "Scripting"})

# Protocols where FC->ESC and ESC->FC Telemetry share the same SERIAL port.
# The ESC->FC Telemetry protocol is implicitly determined by (and must match) the FC->ESC Connection protocol.
ESC_SERIAL_SAME_PORT_PROTOCOLS: tuple[str, ...] = tuple(
    str(v["protocol"])
    for v in SERIAL_PROTOCOLS_DICT.values()
    if v.get("component") == "ESC" and v["protocol"] not in ESC_TELEMETRY_ONLY_PROTOCOLS
)

BATT_MONITOR_CONNECTION: dict[str, dict[str, Union[tuple[str, ...], str]]] = {
    "0": {"type": ("None",), "protocol": "Disabled"},
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

GNSS_RECEIVER_CONNECTION: dict[str, dict[str, Union[tuple[str, ...], str]]] = {
    "0": {"type": ("None",), "protocol": "None"},
    "1": {"type": SERIAL_PORTS, "protocol": "AUTO"},
    "2": {"type": SERIAL_PORTS, "protocol": "uBlox"},
    "5": {"type": SERIAL_PORTS, "protocol": "NMEA"},
    "6": {"type": SERIAL_PORTS, "protocol": "SiRF"},
    "7": {"type": SERIAL_PORTS, "protocol": "HIL"},
    "8": {"type": SERIAL_PORTS, "protocol": "SwiftNav"},
    "9": {"type": CAN_PORTS, "protocol": "DroneCAN"},
    "10": {"type": SERIAL_PORTS, "protocol": "Septentrio(SBF)"},
    "11": {"type": SERIAL_PORTS, "protocol": "Trimble(GSOF)"},
    "13": {"type": SERIAL_PORTS, "protocol": "ERB"},
    "14": {"type": SERIAL_PORTS, "protocol": "MAVLink"},
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
    "26": {"type": SERIAL_PORTS, "protocol": "Septentrio-DualAntenna(SBF)"},
}

# Key: tuple of possible ESC->FC telemetry connection types, or a sentinel such as
# ("same_as_FC_to_ESC",); value: telemetry protocol string for that connection choice.
EscToFcTelemetryDict = dict[tuple[str, ...], str]
ESC_TO_FC_TELEMETRY_NONE: EscToFcTelemetryDict = {("None",): "None"}
ESC_TO_FC_TELEMETRY_SCRIPTING_ONLY: EscToFcTelemetryDict = {("None",): "None", SERIAL_PORTS: "Scripting"}
ESC_TO_FC_TELEMETRY_SERIAL_ONLY: EscToFcTelemetryDict = {("None",): "None", SERIAL_PORTS: "ESC Telemetry"}
ESC_TO_FC_TELEMETRY_DSHOT: EscToFcTelemetryDict = {
    ("None",): "None",
    ("same_as_FC_to_ESC",): "BDShotOnly",
    SERIAL_PORTS: "ESC Telemetry",
}
ESC_TO_FC_TELEMETRY_SAME: EscToFcTelemetryDict = {("same_as_FC_to_ESC",): "same_as_FC_to_ESC"}

# FC->ESC Connection types and protocols determine the possible ESC->FC Telemetry protocols,
# with some variations by vehicle type.
ESC_CONNECTION_DICT: dict[str, dict[str, dict[str, Union[tuple[str, ...], str, EscToFcTelemetryDict]]]] = {
    "ArduCopter": {
        "0": {"type": PWM_OUT_PORTS, "protocol": "Normal", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SCRIPTING_ONLY},
        "1": {"type": PWM_OUT_PORTS, "protocol": "OneShot", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SERIAL_ONLY},
        "2": {"type": PWM_OUT_PORTS, "protocol": "OneShot125", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SERIAL_ONLY},
        "3": {"type": PWM_OUT_PORTS, "protocol": "Brushed", "ESC_to_FC": ESC_TO_FC_TELEMETRY_NONE},
        "4": {"type": PWM_OUT_PORTS, "protocol": "DShot150", "ESC_to_FC": ESC_TO_FC_TELEMETRY_DSHOT},
        "5": {"type": PWM_OUT_PORTS, "protocol": "DShot300", "ESC_to_FC": ESC_TO_FC_TELEMETRY_DSHOT},
        "6": {"type": PWM_OUT_PORTS, "protocol": "DShot600", "ESC_to_FC": ESC_TO_FC_TELEMETRY_DSHOT},
        "7": {"type": PWM_OUT_PORTS, "protocol": "DShot1200", "ESC_to_FC": ESC_TO_FC_TELEMETRY_DSHOT},
        "8": {"type": PWM_OUT_PORTS, "protocol": "PWMRange", "ESC_to_FC": ESC_TO_FC_TELEMETRY_NONE},
        "9": {"type": PWM_OUT_PORTS, "protocol": "PWMAngle", "ESC_to_FC": ESC_TO_FC_TELEMETRY_NONE},
        "100": {"type": SERIAL_PORTS, "protocol": "FETtecOneWire", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SAME},
        "101": {"type": SERIAL_PORTS, "protocol": "Torqeedo", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SAME},
        "102": {"type": SERIAL_PORTS, "protocol": "CoDevESC", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SAME},
        "200": {"type": CAN_PORTS, "protocol": "DroneCAN", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SAME},
    },
    "Heli": {
        "0": {"type": PWM_OUT_PORTS, "protocol": "Normal", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SCRIPTING_ONLY},
        "1": {"type": PWM_OUT_PORTS, "protocol": "OneShot", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SERIAL_ONLY},
        "2": {"type": PWM_OUT_PORTS, "protocol": "OneShot125", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SERIAL_ONLY},
        "3": {"type": PWM_OUT_PORTS, "protocol": "Brushed", "ESC_to_FC": ESC_TO_FC_TELEMETRY_NONE},
        "4": {"type": PWM_OUT_PORTS, "protocol": "DShot150", "ESC_to_FC": ESC_TO_FC_TELEMETRY_DSHOT},
        "5": {"type": PWM_OUT_PORTS, "protocol": "DShot300", "ESC_to_FC": ESC_TO_FC_TELEMETRY_DSHOT},
        "6": {"type": PWM_OUT_PORTS, "protocol": "DShot600", "ESC_to_FC": ESC_TO_FC_TELEMETRY_DSHOT},
        "7": {"type": PWM_OUT_PORTS, "protocol": "DShot1200", "ESC_to_FC": ESC_TO_FC_TELEMETRY_DSHOT},
        "8": {"type": PWM_OUT_PORTS, "protocol": "PWMRange", "ESC_to_FC": ESC_TO_FC_TELEMETRY_NONE},
        "9": {"type": PWM_OUT_PORTS, "protocol": "PWMAngle", "ESC_to_FC": ESC_TO_FC_TELEMETRY_NONE},
        "100": {"type": SERIAL_PORTS, "protocol": "FETtecOneWire", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SAME},
        "101": {"type": SERIAL_PORTS, "protocol": "Torqeedo", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SAME},
        "102": {"type": SERIAL_PORTS, "protocol": "CoDevESC", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SAME},
        "200": {"type": CAN_PORTS, "protocol": "DroneCAN", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SAME},
    },
    "Rover": {
        "0": {"type": PWM_OUT_PORTS, "protocol": "Normal", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SCRIPTING_ONLY},
        "1": {"type": PWM_OUT_PORTS, "protocol": "OneShot", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SERIAL_ONLY},
        "2": {"type": PWM_OUT_PORTS, "protocol": "OneShot125", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SERIAL_ONLY},
        "3": {"type": PWM_OUT_PORTS, "protocol": "BrushedWithRelay", "ESC_to_FC": ESC_TO_FC_TELEMETRY_NONE},
        "4": {"type": PWM_OUT_PORTS, "protocol": "BrushedBiPolar", "ESC_to_FC": ESC_TO_FC_TELEMETRY_NONE},
        "5": {"type": PWM_OUT_PORTS, "protocol": "DShot150", "ESC_to_FC": ESC_TO_FC_TELEMETRY_DSHOT},
        "6": {"type": PWM_OUT_PORTS, "protocol": "DShot300", "ESC_to_FC": ESC_TO_FC_TELEMETRY_DSHOT},
        "7": {"type": PWM_OUT_PORTS, "protocol": "DShot600", "ESC_to_FC": ESC_TO_FC_TELEMETRY_DSHOT},
        "8": {"type": PWM_OUT_PORTS, "protocol": "DShot1200", "ESC_to_FC": ESC_TO_FC_TELEMETRY_DSHOT},
        "9": {"type": PWM_OUT_PORTS, "protocol": "PWMRange", "ESC_to_FC": ESC_TO_FC_TELEMETRY_NONE},
        "10": {"type": PWM_OUT_PORTS, "protocol": "PWMAngle", "ESC_to_FC": ESC_TO_FC_TELEMETRY_NONE},
        "100": {"type": SERIAL_PORTS, "protocol": "FETtecOneWire", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SAME},
        "101": {"type": SERIAL_PORTS, "protocol": "Torqeedo", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SAME},
        "102": {"type": SERIAL_PORTS, "protocol": "CoDevESC", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SAME},
        "200": {"type": CAN_PORTS, "protocol": "DroneCAN", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SAME},
    },
    # ArduPlane uses Q_M_PWM_TYPE instead of MOT_PWM_TYPE and supports DroneCAN for ESCs
    "ArduPlane": {
        "0": {"type": PWM_OUT_PORTS, "protocol": "Normal", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SCRIPTING_ONLY},
        "1": {"type": PWM_OUT_PORTS, "protocol": "OneShot", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SERIAL_ONLY},
        "2": {"type": PWM_OUT_PORTS, "protocol": "OneShot125", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SERIAL_ONLY},
        "3": {"type": PWM_OUT_PORTS, "protocol": "Brushed", "ESC_to_FC": ESC_TO_FC_TELEMETRY_NONE},
        "4": {"type": PWM_OUT_PORTS, "protocol": "DShot150", "ESC_to_FC": ESC_TO_FC_TELEMETRY_DSHOT},
        "5": {"type": PWM_OUT_PORTS, "protocol": "DShot300", "ESC_to_FC": ESC_TO_FC_TELEMETRY_DSHOT},
        "6": {"type": PWM_OUT_PORTS, "protocol": "DShot600", "ESC_to_FC": ESC_TO_FC_TELEMETRY_DSHOT},
        "7": {"type": PWM_OUT_PORTS, "protocol": "DShot1200", "ESC_to_FC": ESC_TO_FC_TELEMETRY_DSHOT},
        "8": {"type": PWM_OUT_PORTS, "protocol": "PWMRange", "ESC_to_FC": ESC_TO_FC_TELEMETRY_NONE},
        "9": {"type": PWM_OUT_PORTS, "protocol": "PWMAngle", "ESC_to_FC": ESC_TO_FC_TELEMETRY_NONE},
        "200": {"type": CAN_PORTS, "protocol": "DroneCAN", "ESC_to_FC": ESC_TO_FC_TELEMETRY_SAME},
    },
}


def get_esc_connection_sub_dict(
    vehicle_type: str,
) -> dict[str, dict[str, Union[tuple[str, ...], str, EscToFcTelemetryDict]]]:
    """Return the vehicle-type-specific entry sub-dict from ESC_CONNECTION_DICT."""
    return ESC_CONNECTION_DICT.get(vehicle_type, ESC_CONNECTION_DICT["ArduCopter"])


# RC_PROTOCOLS is a bitmask parameter, so keys are actual bitmask values (2^bit_position)
# Special case: value 1 = All protocols enabled
# Bit 1 (value 2) = PPM, Bit 2 (value 4) = IBUS, Bit 3 (value 8) = SBUS, etc.
RC_PROTOCOLS_DICT: dict[str, dict[str, Union[tuple[str, ...], str]]] = {
    "1": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "All"},  # Special case: 1 = All protocols
    "2": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "PPM"},  # Bit 1
    "4": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "IBUS"},  # Bit 2
    "8": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "SBUS"},  # Bit 3
    "16": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "SBUS_NI"},  # Bit 4
    "32": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "DSM"},  # Bit 5
    "64": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "SUMD"},  # Bit 6
    "128": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "SRXL"},  # Bit 7
    "256": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "SRXL2"},  # Bit 8
    "512": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "CRSF"},  # Bit 9
    "1024": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "ST24"},  # Bit 10
    "2048": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "FPORT"},  # Bit 11
    "4096": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "FPORT2"},  # Bit 12
    "8192": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "FastSBUS"},  # Bit 13
    "16384": {"type": CAN_PORTS, "protocol": "DroneCAN"},  # Bit 14
    "32768": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "Ghost"},  # Bit 15
    "65536": {"type": RC_PORTS + SERIAL_PORTS, "protocol": "MAVRadio"},  # Bit 16
}

# When adding new entries here, make sure to also update the self._verify_dict_is_uptodate() calls
# inside the process_fc_parameters() method in the data_model_vehicle_components_import.py file
FRAME_CLASS_DICT: dict[str, dict[int, str]] = {
    "ArduCopter": {
        0: "Undefined",
        1: "Quad",
        2: "Hexa",
        3: "Octa",
        4: "OctaQuad",
        5: "Y6",
        6: "Heli",
        7: "Tri",
        8: "SingleCopter",
        9: "CoaxCopter",
        10: "BiCopter",
        11: "Heli_Dual",
        12: "DodecaHexa",
        13: "HeliQuad",
        14: "Deca",
        15: "Scripting Matrix",
        16: "6DoF Scripting",
        17: "Dynamic Scripting Matrix",
    },
    "Heli": {
        0: "Undefined",
        6: "Heli",
        8: "SingleCopter",
        9: "CoaxCopter",
        10: "BiCopter",
        11: "Heli_Dual",
        13: "HeliQuad",
    },
    "Rover": {
        0: "Undefined",
        1: "Rover",
        2: "Boat",
        3: "BalanceBot",
    },
    # ArduPlane does not have a FRAME_CLASS parameter, it uses Q_FRAME_CLASS instead for the same purpose.
    # We added it here to unify and simplify the GUI as they serve the same purpose of defining the number of motors users
    # used in active hover propulsion.
    "ArduPlane": {
        0: "Undefined",
        1: "Quad",
        2: "Hexa",
        3: "Octa",
        4: "OctaQuad",
        5: "Y6",
        7: "Tri",
        10: "Single/Dual",
        12: "DodecaHexa",
        14: "Deca",
        15: "Scripting Matrix",
        17: "Dynamic Scripting Matrix",
    },
}


def get_frame_class_as_protocol_dict(vehicle_type: str) -> dict[str, dict[str, str]]:
    """
    Return the vehicle-type-specific frame class mapping from FRAME_CLASS_DICT.

    Each entry is shaped as a documentation-compatible protocol dictionary so
    _verify_dict_is_uptodate() can handle FRAME_CLASS metadata unchanged.
    """
    return {
        str(frame_class): {"protocol": frame_class_name}
        for frame_class, frame_class_name in FRAME_CLASS_DICT.get(vehicle_type, FRAME_CLASS_DICT["ArduCopter"]).items()
    }


def get_frame_class_valid_tuple(vehicle_type: str) -> tuple[str, ...]:
    """
    Return the valid frame-class labels for the given vehicle type, excluding "Undefined".

    "Undefined" is not a valid user selection and should not appear in the combobox.
    """
    return tuple(v for v in FRAME_CLASS_DICT.get(vehicle_type, FRAME_CLASS_DICT["ArduCopter"]).values() if v != "Undefined")


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
            ("Motors", "Specifications", "Poles"): (int, (2, 59), "Motor Poles"),
            ("Propellers", "Specifications", "Diameter_inches"): (float, (0.3, 400), "Propeller Diameter"),
        }
    )

    def set_component_value(self, path: ComponentPath, value: Union[ComponentData, ComponentValue, None]) -> None:
        ComponentDataModelBase.set_component_value(self, path, value)

        # and change side effects
        if path == ("Battery", "Specifications", "Chemistry") and isinstance(value, str) and self._battery_chemistry != value:
            self._battery_chemistry = value
            for vtype in BATTERY_CELL_VOLTAGE_TYPES:
                self.set_component_value(
                    ("Battery", "Specifications", vtype), BatteryCell.recommended_cell_voltage(value, vtype)
                )

        if path == ("Flight Controller", "Firmware", "Type") and isinstance(value, str):
            self._possible_choices[("Frame", "Specifications", "Frame class")] = get_frame_class_valid_tuple(value)

        # Update possible choices for protocol fields when connection type changes
        self._update_possible_choices_for_path(path, value)

    def _get_current_esc_to_fc_dict(self) -> "EscToFcTelemetryDict":
        """Return the ESC_to_FC dict for the currently selected FC->ESC Type + Protocol entry."""
        fw_type = str(self.get_component_value(("Flight Controller", "Firmware", "Type")) or "")
        fc_esc_conn_type = str(self.get_component_value(("ESC", "FC->ESC Connection", "Type")) or "")
        fc_esc_protocol = str(self.get_component_value(("ESC", "FC->ESC Connection", "Protocol")) or "")
        for entry in get_esc_connection_sub_dict(fw_type).values():
            if fc_esc_conn_type in entry.get("type", ()) and entry.get("protocol") == fc_esc_protocol:
                return cast("EscToFcTelemetryDict", entry.get("ESC_to_FC", {}))
        return {}

    def get_valid_esc_telemetry_types(self) -> tuple[str, ...]:
        """
        Return valid ESC->FC Telemetry Type values for the current FC->ESC connection protocol.

        Uses the ESC_CONNECTION_DICT directly (via _get_current_esc_to_fc_dict) so it does not
        depend on _mot_pwm_types being populated from a doc file.  This makes it safe to call from
        the GUI cascade code regardless of whether a parameter-definition file has been loaded.
        """
        esc_to_fc_dict = self._get_current_esc_to_fc_dict()
        fc_esc_conn_type = str(self.get_component_value(("ESC", "FC->ESC Connection", "Type")) or "")
        valid: list[str] = []
        for port_key in esc_to_fc_dict:
            if port_key == ("same_as_FC_to_ESC",):
                if fc_esc_conn_type not in valid:
                    valid.append(fc_esc_conn_type)
            else:
                for port in port_key:
                    if port not in valid:
                        valid.append(port)
        return tuple(valid) if valid else ("None",)

    def is_esc_telemetry_type_mirrored(self) -> bool:
        """
        Return True when the ESC->FC Telemetry Type combobox should be greyed-out.

        True ONLY when the ESC_to_FC dict has EXACTLY ONE key: ("same_as_FC_to_ESC",).
        This covers fully-mirrored entries like ESC_TO_FC_TELEMETRY_SAME (CAN/DroneCAN and
        SERIAL same-port protocols FETtecOneWire, Torqeedo, CoDevESC).

        False for entries with multiple type keys like ESC_TO_FC_TELEMETRY_DSHOT which has
        ("None",), ("same_as_FC_to_ESC",), and SERIAL_PORTS — these are NOT fully mirrored.
        """
        esc_to_fc_dict = self._get_current_esc_to_fc_dict()
        # Type is mirrored only if the sole key is ("same_as_FC_to_ESC",)
        return list(esc_to_fc_dict) == [("same_as_FC_to_ESC",)]

    def is_esc_telemetry_protocol_mirrored(self) -> bool:
        """
        Return True when the ESC->FC Telemetry Protocol combobox should be greyed-out.

        True when the matching ESC_CONNECTION_DICT entry has "same_as_FC_to_ESC" as a value,
        meaning the telemetry protocol is forced to match the FC->ESC protocol exactly.
        This covers only fully-mirrored entries (ESC_TO_FC_TELEMETRY_SAME: CAN/DroneCAN and
        SERIAL same-port protocols FETtecOneWire, Torqeedo, CoDevESC). BDShot entries have
        ("same_as_FC_to_ESC",) as a key but "BDShotOnly" as the value — not mirrored here.
        """
        return "same_as_FC_to_ESC" in self._get_current_esc_to_fc_dict().values()

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

        fw_type = str(self.get_component_value(("Flight Controller", "Firmware", "Type")) or "")
        fallbacks: dict[str, tuple[str, ...]] = {
            "RC_PROTOCOLS": get_all_protocols(RC_PROTOCOLS_DICT),
            "BATT_MONITOR": get_all_protocols(BATT_MONITOR_CONNECTION),
            "MOT_PWM_TYPE": tuple(
                str(v["protocol"])
                for v in get_esc_connection_sub_dict(fw_type).values()
                if isinstance(v.get("type"), tuple) and v["type"] == PWM_OUT_PORTS
            ),
            "GPS_TYPE": get_all_protocols(GNSS_RECEIVER_CONNECTION),
            "GPS1_TYPE": get_all_protocols(GNSS_RECEIVER_CONNECTION),  # GPS_TYPE was renamed to GPS1_TYPE in 4.6
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
                            type_val if isinstance(type_val, tuple) else [type_val]
                            for type_val in [value["type"] for value in conn_dict.values()]
                        ],
                        [],
                    )
                )
            )

        # Always initialize from the fallback so that PWM protocol choices are available
        # even when no parameter-definition file (apm.pdef.xml) has been loaded (e.g. in tests).
        self._mot_pwm_types = fallbacks["MOT_PWM_TYPE"]
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
            ("ESC", "FC->ESC Connection", "Type"): (*PWM_OUT_PORTS, *SERIAL_PORTS, *CAN_PORTS),
            ("ESC", "FC->ESC Connection", "Protocol"): self._mot_pwm_types,
            ("ESC", "ESC->FC Telemetry", "Type"): ("None", *PWM_OUT_PORTS, *SERIAL_PORTS, *CAN_PORTS),
            ("ESC", "ESC->FC Telemetry", "Protocol"): tuple(
                dict.fromkeys(
                    telem_protocol
                    for entry in get_esc_connection_sub_dict(fw_type).values()
                    if isinstance(entry.get("ESC_to_FC"), dict)
                    for telem_protocol in cast("EscToFcTelemetryDict", entry["ESC_to_FC"]).values()
                    if telem_protocol != "same_as_FC_to_ESC" and telem_protocol not in ESC_SERIAL_SAME_PORT_PROTOCOLS
                )
            ),
            ("GNSS Receiver", "FC Connection", "Type"): ("None", *SERIAL_PORTS, *CAN_PORTS),
            ("GNSS Receiver", "FC Connection", "Protocol"): get_all_protocols(GNSS_RECEIVER_CONNECTION),
            ("Battery", "Specifications", "Chemistry"): BatteryCell.chemistries(),
            ("Frame", "Specifications", "Frame class"): get_frame_class_valid_tuple(fw_type),
        }
        for component in ["RC Receiver", "Telemetry", "Battery Monitor", "ESC", "GNSS Receiver"]:
            if component not in self._data.get("Components", {}):
                continue

            if component == "ESC":
                self._update_possible_choices_for_path(
                    ("ESC", "FC->ESC Connection", "Type"),
                    self.get_component_value(("ESC", "FC->ESC Connection", "Type")),
                )
                self._update_possible_choices_for_path(
                    ("ESC", "ESC->FC Telemetry", "Type"),
                    self.get_component_value(("ESC", "ESC->FC Telemetry", "Type")),
                )
            else:
                self._update_possible_choices_for_path(
                    (component, "FC Connection", "Type"),
                    self.get_component_value((component, "FC Connection", "Type")),
                )

    def _update_esc_fc_connection_choices(self, value: str, protocol_path: ComponentPath) -> None:
        """Update FC->ESC Connection Protocol and cascade ESC->FC Telemetry choices when connection Type changes."""
        # Update FC->ESC Protocol choices based on connection type
        if value == "None":
            self._possible_choices[protocol_path] = ("None",)
        elif value in CAN_PORTS:
            self._possible_choices[protocol_path] = self._get_esc_connection_protocols_for_type(value) or ("None",)
        elif value in SERIAL_PORTS:
            self._possible_choices[protocol_path] = ESC_SERIAL_SAME_PORT_PROTOCOLS
        else:
            # For PWM outputs, use motor PWM types
            self._possible_choices[protocol_path] = self._mot_pwm_types

        # Cascade-update ESC->FC Telemetry Type and Protocol choices
        telemetry_type_path: ComponentPath = ("ESC", "ESC->FC Telemetry", "Type")
        telemetry_protocol_path: ComponentPath = ("ESC", "ESC->FC Telemetry", "Protocol")
        telemetry_types, telemetry_protocols = self._compute_esc_telemetry_choices(value)
        self._possible_choices[telemetry_type_path] = telemetry_types
        self._possible_choices[telemetry_protocol_path] = telemetry_protocols

    def _compute_telem_serial_protocols(
        self,
        telem_type_value: str,
        esc_sub: dict[str, dict[str, Union[tuple[str, ...], str, "EscToFcTelemetryDict"]]],
    ) -> tuple[str, ...]:
        """
        Compute ESC->FC Telemetry Protocol choices when Telemetry Type is a SERIAL port.

        When FC->ESC Type is also SERIAL (same-port mirror mode), returns the matching same-port
        protocol. When FC->ESC Type is PWM/None (independent back-channel), restricts to the
        protocols allowed by the specific current FC->ESC Protocol (e.g., "Normal" only allows
        "Scripting", not "ESC Telemetry" which belongs to DShot/OneShot protocols).
        """
        fc_esc_type = str(self.get_component_value(("ESC", "FC->ESC Connection", "Type")) or "")
        if fc_esc_type in SERIAL_PORTS:
            fc_esc_protocol = str(self.get_component_value(("ESC", "FC->ESC Connection", "Protocol")) or "")
            return (fc_esc_protocol,) if fc_esc_protocol in ESC_SERIAL_SAME_PORT_PROTOCOLS else ("None",)
        # PWM / None: restrict to protocols supported by the currently selected FC->ESC Protocol.
        fc_esc_protocol = str(self.get_component_value(("ESC", "FC->ESC Connection", "Protocol")) or "")
        # Find the ESC_to_FC dict for the current protocol entry.
        esc_to_fc: EscToFcTelemetryDict = {("None",): "None"}
        for entry in esc_sub.values():
            if entry.get("protocol") == fc_esc_protocol:
                raw = entry.get("ESC_to_FC", {("None",): "None"})
                esc_to_fc = cast("EscToFcTelemetryDict", raw)
                break
        return tuple(
            dict.fromkeys(
                telem_protocol
                for port_key, telem_protocol in esc_to_fc.items()
                if isinstance(port_key, tuple)
                and telem_type_value in port_key
                and telem_protocol not in ESC_SERIAL_SAME_PORT_PROTOCOLS
                and telem_protocol != "same_as_FC_to_ESC"
            )
        )

    @staticmethod
    def _collect_telem_choices_from_esc_to_fc(
        esc_to_fc: "EscToFcTelemetryDict", fc_esc_conn_type: str
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """
        Collect ESC->FC Telemetry Type and Protocol choices from a single ESC_to_FC mapping.

        Shared helper used by both _compute_esc_telemetry_choices_union_pwm and
        _compute_esc_telemetry_choices_pwm to avoid duplicating the accumulation loop.
        """
        collected_types: list[str] = ["None"]
        collected_protocols: list[str] = ["None"]
        for port_key, telem_protocol in esc_to_fc.items():
            if telem_protocol == "same_as_FC_to_ESC" or telem_protocol in ESC_SERIAL_SAME_PORT_PROTOCOLS:
                continue
            if port_key == ("None",):
                pass  # "None" already seeded above
            elif port_key == ("same_as_FC_to_ESC",):
                if fc_esc_conn_type not in collected_types:
                    collected_types.append(fc_esc_conn_type)
            else:
                for p in port_key:
                    if p not in collected_types:
                        collected_types.append(p)
            if telem_protocol not in collected_protocols:
                collected_protocols.append(telem_protocol)
        return tuple(collected_types), tuple(collected_protocols)

    def _compute_esc_telemetry_choices_union_pwm(self, fc_esc_conn_type: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """
        Compute ESC->FC Telemetry choices as the union across all PWM protocol options.

        Used when FC->ESC Protocol is stale (e.g., transitioning from CAN) so no single
        protocol is authoritative yet.  Shows every back-channel type/protocol that any
        PWM protocol supports, giving the user the broadest valid choice set.
        """
        fw_type = str(self.get_component_value(("Flight Controller", "Firmware", "Type")) or "")
        esc_sub = get_esc_connection_sub_dict(fw_type)
        union_types: list[str] = ["None"]
        union_protocols: list[str] = ["None"]
        for entry in esc_sub.values():
            if entry.get("type") != PWM_OUT_PORTS:
                continue
            esc_to_fc = cast("EscToFcTelemetryDict", entry.get("ESC_to_FC", {("None",): "None"}))
            types, protocols = self._collect_telem_choices_from_esc_to_fc(esc_to_fc, fc_esc_conn_type)
            for t in types:
                if t not in union_types:
                    union_types.append(t)
            for p in protocols:
                if p not in union_protocols:
                    union_protocols.append(p)
        return tuple(union_types), tuple(union_protocols)

    def _compute_esc_telemetry_choices_pwm(
        self, fc_esc_conn_type: str, current_protocol: str
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Compute ESC->FC Telemetry choices when FC->ESC Connection is a PWM output."""
        fw_type = str(self.get_component_value(("Flight Controller", "Firmware", "Type")) or "")
        esc_sub = get_esc_connection_sub_dict(fw_type)
        esc_to_fc: EscToFcTelemetryDict = {("None",): "None"}
        for entry in esc_sub.values():
            if entry.get("protocol") == current_protocol:
                esc_to_fc = cast("EscToFcTelemetryDict", entry.get("ESC_to_FC", {("None",): "None"}))
                break
        return self._collect_telem_choices_from_esc_to_fc(esc_to_fc, fc_esc_conn_type)

    def _compute_esc_telemetry_choices(self, fc_esc_conn_type: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Compute valid ESC->FC Telemetry Type and Protocol choices for the given FC->ESC Connection Type."""
        if fc_esc_conn_type in CAN_PORTS:
            return (fc_esc_conn_type,), self._get_esc_connection_protocols_for_type(fc_esc_conn_type) or ("None",)
        if fc_esc_conn_type in SERIAL_PORTS:
            # The ESC->FC Telemetry uses the same SERIAL port as the FC->ESC connection.
            # Only the matching same-port protocol is valid (FETtecOneWire, Torqeedo, CoDevESC).
            # This is a mirrored setting and cannot be disabled separately.
            current_protocol = str(self.get_component_value(("ESC", "FC->ESC Connection", "Protocol")) or "")
            if current_protocol in ESC_SERIAL_SAME_PORT_PROTOCOLS:
                return (fc_esc_conn_type,), (current_protocol,)
            return (fc_esc_conn_type,), ("None",)
        if fc_esc_conn_type == "None":
            return ("None",), ("None",)
        # PWM
        current_protocol = str(self.get_component_value(("ESC", "FC->ESC Connection", "Protocol")) or "")
        if current_protocol not in self._mot_pwm_types:
            # Protocol is stale (e.g., transitioning from CAN/SERIAL) — compute the union of
            # all possible PWM back-channel options so the user sees the full valid choice set.
            return self._compute_esc_telemetry_choices_union_pwm(fc_esc_conn_type)
        return self._compute_esc_telemetry_choices_pwm(fc_esc_conn_type, current_protocol)

    def _update_rc_receiver_protocol_choices(self, value: str, protocol_path: ComponentPath) -> None:
        """Update RC Receiver protocol choices based on the selected connection type."""
        if value == "None":
            self._possible_choices[protocol_path] = ("None",)
        else:
            self._possible_choices[protocol_path] = tuple(
                str(v["protocol"]) for v in RC_PROTOCOLS_DICT.values() if value in v["type"]
            )

    def _update_telemetry_protocol_choices(self, value: str, protocol_path: ComponentPath) -> None:
        """Update Telemetry protocol choices based on the selected connection type."""
        if value == "None":
            self._possible_choices[protocol_path] = ("None",)
        else:
            self._possible_choices[protocol_path] = tuple(
                str(v["protocol"]) for v in SERIAL_PROTOCOLS_DICT.values() if v["component"] == "Telemetry"
            )

    def _update_battery_monitor_protocol_choices(self, value: str, protocol_path: ComponentPath) -> None:
        """Update Battery Monitor protocol choices based on the selected connection type."""
        if value == "None":
            self._possible_choices[protocol_path] = ("None",)
            return
        batt_available_protocols: list[str] = [
            str(conn_dict["protocol"])
            for conn_dict in BATT_MONITOR_CONNECTION.values()
            if isinstance(conn_dict["type"], tuple) and value in conn_dict["type"]
        ]
        self._possible_choices[protocol_path] = tuple(batt_available_protocols) if batt_available_protocols else ("None",)

    def _get_esc_connection_protocols_for_type(self, connection_type: str) -> tuple[str, ...]:
        """Return ESC FC->ESC protocols supported by the given connection type for the active vehicle."""
        fw_type = str(self.get_component_value(("Flight Controller", "Firmware", "Type")) or "")
        return tuple(
            dict.fromkeys(
                str(entry["protocol"])
                for entry in get_esc_connection_sub_dict(fw_type).values()
                if isinstance(entry.get("type"), tuple) and connection_type in entry["type"]
            )
        )

    def _update_esc_telemetry_type_protocol_choices(self, value: str, protocol_path: ComponentPath) -> None:
        """Update ESC->FC Telemetry protocol choices based on the selected telemetry type."""
        if value == "None":
            self._possible_choices[protocol_path] = ("None",)
            return
        if value in CAN_PORTS:
            self._possible_choices[protocol_path] = self._get_esc_connection_protocols_for_type(value) or ("None",)
            return
        fw_type = str(self.get_component_value(("Flight Controller", "Firmware", "Type")) or "")
        esc_sub = get_esc_connection_sub_dict(fw_type)
        if value in PWM_OUT_PORTS:
            # BDShot back-channel: collect protocols from ("same_as_FC_to_ESC",) keys
            valid_protocols: tuple[str, ...] = tuple(
                dict.fromkeys(
                    telem_protocol
                    for entry in esc_sub.values()
                    if isinstance(entry.get("ESC_to_FC"), dict)
                    for port_key, telem_protocol in cast("EscToFcTelemetryDict", entry["ESC_to_FC"]).items()
                    if port_key == ("same_as_FC_to_ESC",) and telem_protocol != "same_as_FC_to_ESC"
                )
            )
        else:
            valid_protocols = self._compute_telem_serial_protocols(value, esc_sub)
        self._possible_choices[protocol_path] = valid_protocols or ("None",)

    def _update_gnss_receiver_protocol_choices(self, value: str, protocol_path: ComponentPath) -> None:
        """Update GNSS Receiver protocol choices based on the selected connection type."""
        if value == "None":
            self._possible_choices[protocol_path] = ("None",)
            return
        gnss_available_protocols: list[str] = [
            str(conn_dict["protocol"])
            for conn_dict in GNSS_RECEIVER_CONNECTION.values()
            if isinstance(conn_dict["type"], tuple) and value in conn_dict["type"]
        ]
        self._possible_choices[protocol_path] = tuple(gnss_available_protocols) if gnss_available_protocols else ("None",)

    def _update_possible_choices_for_path(
        self, path: ComponentPath, value: Union[ComponentData, ComponentValue, None]
    ) -> None:
        """Update _possible_choices when connection type values that affect protocol choices are changed."""
        if len(path) < 3 or not isinstance(value, str):
            return

        component_name = path[0]
        section = path[1]

        # When ESC FC->ESC Connection Protocol changes, cascade-update ESC->FC Telemetry Type choices.
        # This ensures the Type widget entries are always consistent with the selected FC->ESC Protocol
        # (e.g., switching from Brushed to DShot expands the type options to include BDShot/SERIAL ports).
        if path[2] == "Protocol" and component_name == "ESC" and section == "FC->ESC Connection":
            fc_esc_type = str(self.get_component_value(("ESC", "FC->ESC Connection", "Type")) or "")
            telem_types, telem_protocols = self._compute_esc_telemetry_choices(fc_esc_type)
            self._possible_choices[("ESC", "ESC->FC Telemetry", "Type")] = telem_types
            self._possible_choices[("ESC", "ESC->FC Telemetry", "Protocol")] = telem_protocols
            return

        if path[2] != "Type":
            return

        if section not in ("FC Connection", "FC->ESC Connection", "ESC->FC Telemetry"):
            return

        protocol_path: ComponentPath = (component_name, section, "Protocol")
        updater = {
            "RC Receiver": self._update_rc_receiver_protocol_choices,
            "Telemetry": self._update_telemetry_protocol_choices,
            "Battery Monitor": self._update_battery_monitor_protocol_choices,
            "GNSS Receiver": self._update_gnss_receiver_protocol_choices,
        }.get(component_name)
        if updater is not None:
            updater(value, protocol_path)
        elif component_name == "ESC":
            if section == "ESC->FC Telemetry":
                self._update_esc_telemetry_type_protocol_choices(value, protocol_path)
            else:  # section == "FC->ESC Connection"
                self._update_esc_fc_connection_choices(value, protocol_path)

    def _validate_tow_limits(self, value: str, path: ComponentPath) -> tuple[str, Optional[float]]:
        """Validate takeoff weight min/max cross-constraints."""
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
        return "", None

    def validate_entry_limits(self, value: str, path: ComponentPath) -> tuple[str, Optional[float]]:
        """
        Validate entry values against limits.

        Returns: (error_message, limited_value) if validation fails, or ("", None) if valid.
        """
        if path in self.VALIDATION_RULES:
            data_type, limits, name = self.VALIDATION_RULES[path]
            try:
                typed_value = data_type(value)
                if typed_value < limits[0] or typed_value > limits[1]:
                    error_msg = _("{name} must be a {data_type_name} between {min} and {max}")
                    limited_value = limits[0] if typed_value < limits[0] else limits[1]
                    type_name = getattr(data_type, "__name__", repr(data_type))
                    return error_msg.format(name=name, data_type_name=type_name, min=limits[0], max=limits[1]), limited_value
            except ValueError:
                error_msg = _("Invalid {data_type_name} value for {name}")
                type_name = getattr(data_type, "__name__", repr(data_type))
                return error_msg.format(data_type_name=type_name, name=name), None

            # Validate takeoff weight limits
            if path[0] == "Frame" and path[1] == "Specifications" and "TOW" in path[2]:
                return self._validate_tow_limits(value, path)

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
                lim = self.get_component_value(("Battery", "Specifications", "Volt per cell arm"))
                return self.validate_against_another_value(voltage, lim, "Volt per cell arm", above=True, delta=0.01)

            # Makes no sense to arm a vehicle at a voltage lower than low voltage as that would trigger a failsafe immediately
            if path[-1] == "Volt per cell arm":
                lim = self.get_component_value(("Battery", "Specifications", "Volt per cell max"))
                err_msg, corr = self.validate_against_another_value(voltage, lim, "Volt per cell max", above=False, delta=0.01)
                if err_msg:
                    return err_msg, corr
                lim = self.get_component_value(("Battery", "Specifications", "Volt per cell low"))
                return self.validate_against_another_value(voltage, lim, "Volt per cell low", above=True, delta=0.01)

            if path[-1] == "Volt per cell low":
                lim = self.get_component_value(("Battery", "Specifications", "Volt per cell arm"))
                err_msg, corr = self.validate_against_another_value(voltage, lim, "Volt per cell arm", above=False, delta=0.01)
                if err_msg:
                    return err_msg, corr
                lim = self.get_component_value(("Battery", "Specifications", "Volt per cell crit"))
                return self.validate_against_another_value(voltage, lim, "Volt per cell crit", above=True, delta=0.01)

            # There is no monotonicity requirement for Volt per cell crit and Volt per cell min, they just both need to be
            # below Volt per cell low, so they are validated independently against those limits, not against each other
            if path[-1] == "Volt per cell crit":
                lim = self.get_component_value(("Battery", "Specifications", "Volt per cell low"))
                return self.validate_against_another_value(voltage, lim, "Volt per cell low", above=False, delta=0.01)

            if path[-1] == "Volt per cell min":
                lim = self.get_component_value(("Battery", "Specifications", "Volt per cell low"))
                return self.validate_against_another_value(voltage, lim, "Volt per cell low", above=False, delta=0.01)

        return "", None

    def recommended_cell_voltage(self, path: ComponentPath) -> float:
        """Get recommended cell voltage based on the path."""
        if path[-1] in BATTERY_CELL_VOLTAGE_TYPES:
            return BatteryCell.recommended_cell_voltage(self._battery_chemistry, path[-1])
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

    def _validate_limits_and_voltages(self, path: ComponentPath, value: str, paths_str: str, errors: list[str]) -> None:
        """Validate entry limits and battery voltages."""
        if path in self.VALIDATION_RULES:
            error_msg, corrected_value = self.validate_entry_limits(value, path)
            if error_msg:
                errors.append(error_msg.format(value=value, paths_str=paths_str))
                if corrected_value is not None:
                    self.set_component_value(path, corrected_value)
                return

        if path in BATTERY_CELL_VOLTAGE_PATHS:
            error_msg, corrected_value = self.validate_cell_voltage(value, path)
            if error_msg:
                errors.append(error_msg.format(value=value, paths_str=paths_str))
                if corrected_value is not None:
                    self.set_component_value(path, corrected_value)
                return

        self._validate_motor_poles(errors, path, value, paths_str)

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

            # Keep protocol choices in sync with connection type changes in this batch.
            # This ensures dependent fields like Battery Monitor protocol are validated correctly
            # when both Type and Protocol are present in entry_values.
            if len(path) >= 3 and path[2] == "Type" and isinstance(value, str):
                self._update_possible_choices_for_path(path, value)

            # Check for duplicate connections
            esc_conn_sections = {"FC->ESC Connection", "ESC->FC Telemetry"}
            is_fc_conn_type = (
                len(path) >= 3 and path[2] == "Type" and (path[1] == "FC Connection" or path[1] in esc_conn_sections)
            )
            if is_fc_conn_type:
                # Type assertion: path has at least 3 elements as checked above
                if len(path) < 3:
                    continue  # Help type checker understand that path[2] is safe to access
                if value in fc_serial_connection and value not in {"CAN1", "CAN2", "I2C1", "I2C2", "I2C3", "I2C4", "None"}:
                    # Allow certain combinations
                    if path[0] in {"Telemetry", "RC Receiver"} and fc_serial_connection[value] in {"Telemetry", "RC Receiver"}:
                        continue

                    # Allow ESC->FC Telemetry to share the same port as FC->ESC Connection (bidirectional serial)
                    if path[0] == "ESC" and path[1] in esc_conn_sections and fc_serial_connection[value] == "ESC":
                        continue

                    error_msg = _("Duplicate FC connection type '{value}' for {paths_str}")
                    errors.append(error_msg.format(value=value, paths_str=paths_str))
                    continue
                fc_serial_connection[value] = path[0]

            # Validate limits and voltages
            self._validate_limits_and_voltages(path, value, paths_str, errors)

        return len(errors) == 0, errors

    def _validate_motor_poles(self, errors: list, path: ComponentPath, value: str, paths_str: str) -> None:
        if path == ("Motors", "Specifications", "Poles"):
            # Number of magnetic rotor poles must be even
            # On a common 12N14P BLDC/PMSM motor this is 14, the P number
            try:
                poles = int(value)
                if poles % 2 != 0:
                    error_msg = _("Number of magnetic rotor poles must be even for {paths_str}")
                    errors.append(error_msg.format(paths_str=paths_str))
            except ValueError:
                error_msg = _("Invalid integer value for {paths_str}")
                errors.append(error_msg.format(paths_str=paths_str))

    def correct_display_values_in_loaded_data(self) -> None:
        """
        Correct display values that may have been stored in JSON instead of key values.

        After loading data from JSON, some fields may have display values (e.g., "SERIAL1 (GPS1)")
        instead of key values (e.g., "SERIAL1"). This method corrects such values using the
        display-to-key mapping built during initialization.

        This ensures data integrity without requiring pre-save synchronization in the GUI.
        """
        for path in self._data["Components"]:
            self._correct_values_recursive(self._data["Components"][path], path)

    def _correct_values_recursive(self, data: dict[str, Any], path: ComponentPath) -> None:
        """
        Recursively correct display values in nested component data.

        Args:
            data: Component data dictionary to correct
            path: Current path in the component hierarchy

        """
        for key, value in data.items():
            current_path: ComponentPath = (*path, key)

            if isinstance(value, dict):
                # Recurse into nested dictionaries
                self._correct_values_recursive(value, current_path)
            elif isinstance(value, str) and value in SERIAL_DISPLAY_TO_KEY:
                # This is a display label, use the pre-computed reverse mapping for O(1) lookup
                data[key] = SERIAL_DISPLAY_TO_KEY[value]
