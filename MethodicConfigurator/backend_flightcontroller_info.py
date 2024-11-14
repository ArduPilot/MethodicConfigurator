#!/usr/bin/env python3

"""
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pymavlink import mavutil

# import pymavlink.dialects.v20.ardupilotmega


class BackendFlightcontrollerInfo:  # pylint: disable=too-many-instance-attributes
    """
    Handle flight controller information.

    It includes methods for setting various attributes such as system ID, component ID,
    autopilot type, vehicle type, and capabilities among others.
    """

    def __init__(self):
        self.system_id: str = ""
        self.component_id: str = ""
        self.autopilot: str = ""
        self.vehicle_type: str = ""
        self.mav_type: str = ""
        self.flight_sw_version: str = ""
        self.flight_sw_version_and_type: str = ""
        self.board_version: str = ""
        self.flight_custom_version: str = ""
        self.os_custom_version: str = ""
        self.vendor: str = ""
        self.vendor_id: str = ""
        self.vendor_and_vendor_id: str = ""
        self.product: str = ""
        self.product_id: str = ""
        self.product_and_product_id: str = ""
        self.capabilities: str = ""

        self.is_supported = False
        self.is_mavftp_supported = False

    def get_info(self):
        return {
            "Vendor": self.vendor_and_vendor_id,
            "Product": self.product_and_product_id,
            "Hardware Version": self.board_version,
            "Autopilot Type": self.autopilot,
            "ArduPilot FW Type": self.vehicle_type,
            "MAV Type": self.mav_type,
            "Firmware Version": self.flight_sw_version_and_type,
            "Git Hash": self.flight_custom_version,
            "OS Git Hash": self.os_custom_version,
            "Capabilities": self.capabilities,
            "System ID": self.system_id,
            "Component ID": self.component_id,
        }

    def set_system_id_and_component_id(self, system_id, component_id):
        self.system_id = system_id
        self.component_id = component_id

    def set_autopilot(self, autopilot):
        self.autopilot = self.__decode_mav_autopilot(autopilot)
        self.is_supported = autopilot == mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA

    def set_type(self, mav_type):
        self.vehicle_type = self.__classify_vehicle_type(mav_type)
        self.mav_type = self.__decode_mav_type(mav_type)

    def set_flight_sw_version(self, version):
        v_major, v_minor, v_patch, v_fw_type = self.__decode_flight_sw_version(version)
        self.flight_sw_version = f"{v_major}.{v_minor}.{v_patch}"
        self.flight_sw_version_and_type = self.flight_sw_version + " " + v_fw_type

    def set_board_version(self, board_version):
        self.board_version = board_version

    def set_flight_custom_version(self, flight_custom_version):
        self.flight_custom_version = "".join(chr(c) for c in flight_custom_version)

    def set_os_custom_version(self, os_custom_version):
        self.os_custom_version = "".join(chr(c) for c in os_custom_version)

    def set_vendor_id_and_product_id(self, vendor_id, product_id):
        pid_vid_dict = self.__list_ardupilot_supported_usb_pid_vid()

        self.vendor_id = f"0x{vendor_id:04X}" if vendor_id else "Unknown"
        if vendor_id and vendor_id in pid_vid_dict:
            self.vendor = f"{pid_vid_dict[vendor_id]['vendor']}"
        elif vendor_id:
            self.vendor = "Unknown"
        self.vendor_and_vendor_id = f"{self.vendor} ({self.vendor_id})"

        self.product_id = f"0x{product_id:04X}" if product_id else "Unknown"
        if vendor_id and product_id and product_id in pid_vid_dict[vendor_id]["PID"]:
            self.product = f"{pid_vid_dict[vendor_id]['PID'][product_id]}"
        elif product_id:
            self.product = "Unknown"
        self.product_and_product_id = f"{self.product} ({self.product_id})"

    def set_capabilities(self, capabilities):
        self.capabilities = self.__decode_flight_capabilities(capabilities)
        self.is_mavftp_supported = capabilities & mavutil.mavlink.MAV_PROTOCOL_CAPABILITY_FTP

    @staticmethod
    def __decode_flight_sw_version(flight_sw_version):
        """decode 32 bit flight_sw_version mavlink parameter
        corresponds to ArduPilot encoding in  GCS_MAVLINK::send_autopilot_version"""
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
    def __decode_flight_capabilities(capabilities):
        """Decode 32 bit flight controller capabilities bitmask mavlink parameter.
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
    def __decode_mav_type(mav_type):
        return mavutil.mavlink.enums["MAV_TYPE"].get(mav_type, mavutil.mavlink.EnumEntry("None", "Unknown type")).description

    @staticmethod
    def __decode_mav_autopilot(mav_autopilot):
        return (
            mavutil.mavlink.enums["MAV_AUTOPILOT"]
            .get(mav_autopilot, mavutil.mavlink.EnumEntry("None", "Unknown type"))
            .description
        )

    @staticmethod
    def __classify_vehicle_type(mav_type_int):
        """
        Classify the vehicle type based on the MAV_TYPE enum.

        Parameters:
        mav_type_int (int): The MAV_TYPE enum value.

        Returns:
        str: The classified vehicle type.
        """
        # Define the mapping from MAV_TYPE_* integer to vehicle type category
        mav_type_to_vehicle_type = {
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
        return mav_type_to_vehicle_type.get(mav_type_int)

    @staticmethod
    def __list_ardupilot_supported_usb_pid_vid():
        """
        List all ArduPilot supported USB vendor ID (VID) and product ID (PID).

        source: https://ardupilot.org/dev/docs/USB-IDs.html
        """
        return {
            0x0483: {"vendor": "ST Microelectronics", "PID": {0x5740: "ChibiOS"}},
            0x1209: {
                "vendor": "ArduPilot",
                "PID": {
                    0x5740: "MAVLink",
                    0x5741: "Bootloader",
                },
            },
            0x16D0: {"vendor": "ArduPilot", "PID": {0x0E65: "MAVLink"}},
            0x26AC: {"vendor": "3D Robotics", "PID": {}},
            0x2DAE: {
                "vendor": "CubePilot",
                "PID": {
                    0x1001: "CubeBlack bootloader",
                    0x1011: "CubeBlack",
                    0x1101: "CubeBlack+",
                    0x1002: "CubeYellow bootloader",
                    0x1012: "CubeYellow",
                    0x1005: "CubePurple bootloader",
                    0x1015: "CubePurple",
                    0x1016: "CubeOrange",
                    0x1058: "CubeOrange+",
                    0x1059: "CubeRed",
                },
            },
            0x3162: {"vendor": "Holybro", "PID": {0x004B: "Durandal"}},
            0x27AC: {
                "vendor": "Laser Navigation",
                "PID": {
                    0x1151: "VRBrain-v51",
                    0x1152: "VRBrain-v52",
                    0x1154: "VRBrain-v54",
                    0x1910: "VRCore-v10",
                    0x1351: "VRUBrain-v51",
                },
            },
        }
