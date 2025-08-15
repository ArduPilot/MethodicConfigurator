"""
Manages FC information using FC interface.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections.abc import Sequence
from logging import info as logging_info
from typing import Union

from pymavlink import mavutil

# import pymavlink.dialects.v20.ardupilotmega
from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.data_model_fc_ids import (
    APJ_BOARD_ID_MCU_SERIES_DICT,
    APJ_BOARD_ID_NAME_DICT,
    APJ_BOARD_ID_VENDOR_DICT,
    VID_PID_PRODUCT_DICT,
    VID_VENDOR_DICT,
)


class BackendFlightcontrollerInfo:  # pylint: disable=too-many-instance-attributes
    """
    Handle flight controller information.

    It includes methods for setting various attributes such as system ID, component ID,
    autopilot type, vehicle type, and capabilities among others.
    """

    def __init__(self) -> None:
        self.system_id: str = ""
        self.component_id: str = ""
        self.autopilot: str = ""
        self.vehicle_type: str = ""
        self.firmware_type: str = ""
        self.mav_type: str = ""
        self.flight_sw_version: str = ""
        self.flight_sw_version_and_type: str = ""
        self.board_version: str = ""
        self.apj_board_id: str = ""
        self.flight_custom_version: str = ""
        self.os_custom_version: str = ""
        self.vendor: str = ""
        self.vendor_id: str = ""
        self.vendor_and_vendor_id: str = ""
        self.product: str = ""
        self.product_id: str = ""
        self.product_and_product_id: str = ""
        self.mcu_series: str = ""
        self.capabilities: dict[str, str] = {}

        self.is_supported = False
        self.is_mavftp_supported = False

    def get_info(self) -> dict[str, Union[str, dict[str, str]]]:
        return {
            _("USB Vendor"): self.vendor_and_vendor_id,
            _("USB Product"): self.product_and_product_id,
            _("Board Type"): self.apj_board_id,
            _("Hardware Version"): self.board_version,
            _("Autopilot Type"): self.autopilot,
            _("ArduPilot Vehicle Type"): self.vehicle_type,
            _("ArduPilot FW Type"): self.firmware_type,
            _("MAV Type"): self.mav_type,
            _("Firmware Version"): self.flight_sw_version_and_type,
            _("Git Hash"): self.flight_custom_version,
            _("OS Git Hash"): self.os_custom_version,
            _("Capabilities"): self.capabilities,
            _("System ID"): self.system_id,
            _("Component ID"): self.component_id,
            _("MCU Series"): self.mcu_series,
        }

    def set_system_id_and_component_id(self, system_id: str, component_id: str) -> None:
        self.system_id = system_id
        self.component_id = component_id

    def set_autopilot(self, autopilot: int) -> None:
        self.autopilot = self.__decode_mav_autopilot(autopilot)
        self.is_supported = autopilot == mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA

    def set_type(self, mav_type: int) -> None:
        self.vehicle_type = self.__classify_vehicle_type(mav_type)
        self.mav_type = self.__decode_mav_type(mav_type)

    def set_flight_sw_version(self, version: int) -> None:
        v_major, v_minor, v_patch, v_fw_type = self.__decode_flight_sw_version(version)
        self.flight_sw_version = f"{v_major}.{v_minor}.{v_patch}"
        self.flight_sw_version_and_type = self.flight_sw_version + " " + v_fw_type

    def set_board_version(self, board_version: int) -> None:
        self.board_version = str(board_version & 0x0FFFF)
        apj_board_id = board_version >> 16
        self.apj_board_id = str(apj_board_id)
        self.firmware_type = str(",".join(APJ_BOARD_ID_NAME_DICT.get(apj_board_id, [_("Unknown")])))

        vendor_derived_from_apj_board_id = str(",".join(APJ_BOARD_ID_VENDOR_DICT.get(apj_board_id, ["ArduPilot"])))
        if vendor_derived_from_apj_board_id != "ArduPilot" and self.vendor in ["ArduPilot", _("Unknown")]:
            self.vendor = vendor_derived_from_apj_board_id
        self.mcu_series = str(",".join(APJ_BOARD_ID_MCU_SERIES_DICT.get(apj_board_id, [_("Unknown")])))

    def set_flight_custom_version(self, flight_custom_version: Sequence[int]) -> None:
        self.flight_custom_version = "".join(chr(c) for c in flight_custom_version)

    def set_os_custom_version(self, os_custom_version: Sequence[int]) -> None:
        self.os_custom_version = "".join(chr(c) for c in os_custom_version)

    def set_usb_vendor_and_product_ids(self, vendor_id: int, product_id: int) -> None:
        self.vendor_id = f"0x{vendor_id:04X}" if vendor_id else _("Unknown")
        self.vendor = str(",".join(VID_VENDOR_DICT.get(vendor_id, [_("Unknown")])))
        self.vendor_and_vendor_id = f"{self.vendor} ({self.vendor_id})"

        self.product_id = f"0x{product_id:04X}" if product_id else _("Unknown")
        self.product = str(",".join(VID_PID_PRODUCT_DICT.get((vendor_id, product_id), [_("Unknown")])))
        self.product_and_product_id = f"{self.product} ({self.product_id})"

    def set_capabilities(self, capabilities: int) -> None:
        self.capabilities = self.__decode_flight_capabilities(capabilities)
        self.is_mavftp_supported = bool(capabilities & mavutil.mavlink.MAV_PROTOCOL_CAPABILITY_FTP)

    @staticmethod
    def __decode_flight_sw_version(flight_sw_version: int) -> tuple[int, int, int, str]:
        """
        Decode 32 bit flight_sw_version mavlink parameter.

        corresponds to ArduPilot encoding in  GCS_MAVLINK::send_autopilot_version.
        """
        fw_type_id = (flight_sw_version >> 0) % 256  # E221, E222
        patch = (flight_sw_version >> 8) % 256  # E221, E222
        minor = (flight_sw_version >> 16) % 256  # E221
        major = (flight_sw_version >> 24) % 256  # E221
        if fw_type_id == 0:
            fw_type = "dev"
        elif fw_type_id == 64:
            fw_type = "alpha"
        elif fw_type_id == 128:
            fw_type = "beta"
        elif fw_type_id == 192:
            fw_type = "rc"
        elif fw_type_id == 255:
            fw_type = "official"
        else:
            fw_type = "undefined"
        return major, minor, patch, fw_type

    @staticmethod
    def __decode_flight_capabilities(capabilities: int) -> dict[str, str]:
        """
        Decode 32 bit flight controller capabilities bitmask mavlink parameter.

        Returns a dict of concise English descriptions of each active capability.
        """
        capabilities_dict: dict[str, str] = {}

        # Iterate through each bit in the capabilities bitmask
        for bit in range(32):
            # Check if the bit is set
            if capabilities & (1 << bit):
                # Use the bit value to get the corresponding capability enum
                capability = mavutil.mavlink.enums["MAV_PROTOCOL_CAPABILITY"].get(1 << bit, "Unknown capability")

                if hasattr(capability, "description"):
                    # Append the abbreviated name and description of the capability dictionary
                    capabilities_dict[capability.name.replace("MAV_PROTOCOL_CAPABILITY_", "")] = capability.description
                else:
                    capabilities_dict[f"BIT{bit}"] = capability

        return capabilities_dict

    # see for more info:
    # import pymavlink.dialects.v20.ardupilotmega
    # pymavlink.dialects.v20.ardupilotmega.enums["MAV_TYPE"]
    @staticmethod
    def __decode_mav_type(mav_type: int) -> str:
        return str(
            mavutil.mavlink.enums["MAV_TYPE"].get(mav_type, mavutil.mavlink.EnumEntry("None", "Unknown type")).description
        )

    @staticmethod
    def __decode_mav_autopilot(mav_autopilot: int) -> str:
        return str(
            mavutil.mavlink.enums["MAV_AUTOPILOT"]
            .get(mav_autopilot, mavutil.mavlink.EnumEntry("None", "Unknown type"))
            .description
        )

    @staticmethod
    def __classify_vehicle_type(mav_type_int: int) -> str:
        """
        Classify the vehicle type based on the MAV_TYPE enum.

        Args:
            mav_type_int (int): The MAV_TYPE enum value.

        Returns:
            str: The classified vehicle type.

        """
        # Define the mapping from MAV_TYPE_* integer to vehicle type category
        mav_type_to_vehicle_type: dict[int, str] = {
            mavutil.mavlink.MAV_TYPE_FIXED_WING: "ArduPlane",
            mavutil.mavlink.MAV_TYPE_QUADROTOR: "ArduCopter",
            mavutil.mavlink.MAV_TYPE_COAXIAL: "Heli",
            mavutil.mavlink.MAV_TYPE_HELICOPTER: "Heli",
            mavutil.mavlink.MAV_TYPE_ANTENNA_TRACKER: "AntennaTracker",
            mavutil.mavlink.MAV_TYPE_GCS: "AP_Periph",
            mavutil.mavlink.MAV_TYPE_AIRSHIP: "ArduBlimp",
            mavutil.mavlink.MAV_TYPE_FREE_BALLOON: "ArduBlimp",
            mavutil.mavlink.MAV_TYPE_ROCKET: "ArduCopter",
            mavutil.mavlink.MAV_TYPE_GROUND_ROVER: "Rover",
            mavutil.mavlink.MAV_TYPE_SURFACE_BOAT: "Rover",
            mavutil.mavlink.MAV_TYPE_SUBMARINE: "ArduSub",
            mavutil.mavlink.MAV_TYPE_HEXAROTOR: "ArduCopter",
            mavutil.mavlink.MAV_TYPE_OCTOROTOR: "ArduCopter",
            mavutil.mavlink.MAV_TYPE_TRICOPTER: "ArduCopter",
            mavutil.mavlink.MAV_TYPE_FLAPPING_WING: "ArduPlane",
            mavutil.mavlink.MAV_TYPE_KITE: "ArduPlane",
            mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER: "AP_Periph",
            mavutil.mavlink.MAV_TYPE_VTOL_DUOROTOR: "ArduPlane",
            mavutil.mavlink.MAV_TYPE_VTOL_QUADROTOR: "ArduPlane",
            mavutil.mavlink.MAV_TYPE_VTOL_TILTROTOR: "ArduPlane",
            mavutil.mavlink.MAV_TYPE_VTOL_RESERVED2: "ArduPlane",
            mavutil.mavlink.MAV_TYPE_VTOL_RESERVED3: "ArduPlane",
            mavutil.mavlink.MAV_TYPE_VTOL_RESERVED4: "ArduPlane",
            mavutil.mavlink.MAV_TYPE_VTOL_RESERVED5: "ArduPlane",
            mavutil.mavlink.MAV_TYPE_GIMBAL: "AP_Periph",
            mavutil.mavlink.MAV_TYPE_ADSB: "AP_Periph",
            mavutil.mavlink.MAV_TYPE_PARAFOIL: "ArduPlane",
            mavutil.mavlink.MAV_TYPE_DODECAROTOR: "ArduCopter",
            mavutil.mavlink.MAV_TYPE_CAMERA: "AP_Periph",
            mavutil.mavlink.MAV_TYPE_CHARGING_STATION: "AP_Periph",
            mavutil.mavlink.MAV_TYPE_FLARM: "AP_Periph",
            mavutil.mavlink.MAV_TYPE_SERVO: "AP_Periph",
            mavutil.mavlink.MAV_TYPE_ODID: "AP_Periph",
            mavutil.mavlink.MAV_TYPE_DECAROTOR: "ArduCopter",
            mavutil.mavlink.MAV_TYPE_BATTERY: "AP_Periph",
            mavutil.mavlink.MAV_TYPE_PARACHUTE: "AP_Periph",
            mavutil.mavlink.MAV_TYPE_LOG: "AP_Periph",
            mavutil.mavlink.MAV_TYPE_OSD: "AP_Periph",
            mavutil.mavlink.MAV_TYPE_IMU: "AP_Periph",
            mavutil.mavlink.MAV_TYPE_GPS: "AP_Periph",
            mavutil.mavlink.MAV_TYPE_WINCH: "AP_Periph",
            # Add more mappings as needed
        }

        # Return the classified vehicle type based on the MAV_TYPE enum
        return mav_type_to_vehicle_type.get(mav_type_int, "")

    def log_flight_controller_info(self) -> None:
        """Log flight controller information at INFO level."""
        logging_info("Firmware Version: %s", self.flight_sw_version_and_type)
        logging_info("Firmware first 8 hex bytes of the FC git hash: %s", self.flight_custom_version)
        logging_info("Firmware first 8 hex bytes of the ChibiOS git hash: %s", self.os_custom_version)
        logging_info("Flight Controller firmware type: %s (%s)", self.firmware_type, self.apj_board_id)
        logging_info("Flight Controller HW / board version: %s", self.board_version)
        logging_info("Flight Controller USB vendor ID: %s", self.vendor)
        logging_info("Flight Controller USB product ID: %s", self.product)

    def format_display_value(self, value: Union[str, dict[str, str], None]) -> str:
        """Format a value for display in the UI."""
        if value:
            if isinstance(value, dict):
                return ", ".join(value.keys())
            return str(value)
        return _("N/A")
