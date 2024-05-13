#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

(C) 2024 Amilcar do Carmo Lucas, IAV GmbH

SPDX-License-Identifier:    GPL-3
'''

from logging import debug as logging_debug
from logging import info as logging_info
from logging import warning as logging_warning
from logging import error as logging_error

# import sys
from time import sleep as time_sleep
from os import path as os_path
from os import name as os_name
from os import readlink as os_readlink
from typing import Dict
# import usb.core
# import usb.util
import serial.tools.list_ports
import serial.tools.list_ports_common

from serial.serialutil import SerialException
from MethodicConfigurator.annotate_params import Par

# adding all this allows pyinstaller to build a working windows executable
# note that using --hidden-import does not work for these modules
try:
    from pymavlink import mavutil
    # import pymavlink.dialects.v20.ardupilotmega
except Exception: # pylint: disable=broad-exception-caught
    pass

# Get the current directory
# current_dir = os_path.dirname(os_path.abspath(__file__))

# Add the current directory to the PATH environment variable
# os.environ['PATH'] = os.environ['PATH'] + os.pathsep + current_dir

preferred_ports = [
    '*FTDI*',
    "*Arduino_Mega_2560*",
    "*3D*",
    "*USB_to_UART*",
    '*Ardu*',
    '*PX4*',
    '*Hex_*',
    '*Holybro_*',
    '*mRo*',
    '*FMU*',
    '*Swift-Flyer*',
    '*Serial*',
    '*CubePilot*',
    '*Qiotek*',
]


class FakeSerialForUnitTests():
    """
    A mock serial class for unit testing purposes.

    This class simulates the behavior of a serial connection for testing purposes,
    allowing for the testing of serial communication without needing a physical
    serial device. It includes methods for reading, writing, and checking the
    number of bytes in the input buffer, as well as closing the connection.
    """
    def __init__(self, device: str):
        self.device = device

    def read(self, _len):
        return ""

    def write(self, _buf):
        raise Exception("write always fails")  # pylint: disable=broad-exception-raised

    def inWaiting(self):  # pylint: disable=invalid-name
        return 0

    def close(self):
        pass


class FlightController:  # pylint: disable=too-many-instance-attributes
    """
    A class to manage the connection and parameters of a flight controller.

    Attributes:
        device (str): The connection string to the flight controller.
        master (mavutil.mavlink_connection): The MAVLink connection object.
        fc_parameters (Dict[str, float]): A dictionary of flight controller parameters.
    """
    def __init__(self, reboot_time: int):
        """
        Initialize the FlightController communication object.

        """
        # warn people about ModemManager which interferes badly with ArduPilot
        if os_path.exists("/usr/sbin/ModemManager"):
            logging_warning("You should uninstall ModemManager as it conflicts with ArduPilot")

        self.__reboot_time = reboot_time
        self.__connection_tuples = []
        self.discover_connections()
        self.master = None
        self.comport = None
        self.fc_parameters = {}
        self.__target_system = None
        self.__target_component = None
        self.__capabilities = None
        self.version = None
        self.vehicle_type = None

    def discover_connections(self):
        comports = FlightController.__list_serial_ports()
        usbports = FlightController.__list_usb_devices()
        netports = FlightController.__list_network_ports()
        # list of tuples with the first element being the port name and the second element being the port description
        self.__connection_tuples = [(port.device, port.description) for port in comports] + \
            [(port, port) for port in usbports] + \
            [(port, port) for port in netports]
        logging_info('Available connection ports are:')
        for port in self.__connection_tuples:
            logging_info("%s - %s", port[0], port[1])
        # now that it is logged, add the 'Add another' tuple
        self.__connection_tuples += [tuple(['Add another', 'Add another'])]

    def disconnect(self):
        """
        Close the connection to the flight controller.
        """
        if self.master is not None:
            self.master.close()
            self.master = None
        self.fc_parameters = {}
        self.__target_system = None
        self.__target_component = None
        self.__capabilities = None
        self.version = None

    def add_connection(self, connection_string: str):
        """
        Add a new connection to the list of available connections.
        """
        if connection_string:
            # Check if connection_string is not the first element of any tuple in self.other_connection_tuples
            if all(connection_string != t[0] for t in self.__connection_tuples):
                self.__connection_tuples.insert(-1, (connection_string, connection_string))
                logging_debug("Added connection %s", connection_string)
                return True
            logging_debug("Did not add duplicated connection %s", connection_string)
        else:
            logging_debug("Did not add empty connection")
        return False

    def connect(self, device: str, progress_callback=None):
        """
        Establishes a connection to the FlightController using a specified device.

        This method attempts to connect to the FlightController using the provided device
        connection string. If no device is specified, it attempts to auto-detect a serial
        port that matches the preferred ports list. If a device is specified as 'test',
        it sets some test parameters for debugging purposes.

        Args:
            device (str): The connection string to the flight controller. If an empty string
                        is provided, the method attempts to auto-detect a serial port.
            progress_callback (callable, optional): A callback function to report the progress
                                                    of the connection attempt. Defaults to None.

        Returns:
            str: An error message if the connection fails, otherwise an empty string indicating
                a successful connection.
        """
        if device:
            if device == 'none':
                return ''
            self.add_connection(device)
            self.comport = mavutil.SerialPort(device=device, description=device)
        else:
            autodetect_serial = self.__auto_detect_serial()
            if autodetect_serial:
                # Resolve the soft link if it's a Linux system
                if os_name == 'posix':
                    try:
                        dev = autodetect_serial[0].device
                        logging_debug("Auto-detected device %s", dev)
                        # Get the directory part of the soft link
                        softlink_dir = os_path.dirname(dev)
                        # Resolve the soft link and join it with the directory part
                        resolved_path = os_path.abspath(os_path.join(softlink_dir, os_readlink(dev)))
                        autodetect_serial[0].device = resolved_path
                        logging_debug("Resolved soft link %s to %s", dev, resolved_path)
                    except OSError:
                        pass # Not a soft link, proceed with the original device path
                self.comport = autodetect_serial[0]
                # Add the detected serial port to the list of available connections if it is not there
                if self.comport.device not in [t[0] for t in self.__connection_tuples]:
                    self.__connection_tuples.insert(-1, (self.comport.device, self.comport.description))
            else:
                return "No serial ports found. Please connect a flight controller and try again."
        error_message = self.__create_connection_with_retry(progress_callback=progress_callback)
        return error_message

    def __request_message(self, message_id: int):
        self.master.mav.command_long_send(
            self.__target_system,
            self.__target_component,
            mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE,
            0, # confirmation
            message_id, 0, 0, 0, 0, 0, 0)

    def __cmd_version(self):
        '''show version'''
        self.__request_message(mavutil.mavlink.MAVLINK_MSG_ID_AUTOPILOT_VERSION)

    def __create_connection_with_retry(self, progress_callback, retries: int = 3, # pylint: disable=too-many-return-statements
                                       timeout: int = 5) -> mavutil.mavlink_connection:
        """
        Attempts to create a connection to the flight controller with retries.

        This method attempts to establish a connection to the flight controller using the
        provided device connection string. It will retry the connection attempt up to the
        specified number of retries if the initial attempt fails. The method also supports
        a progress callback to report the progress of the connection attempt.

        Args:
            progress_callback (callable, optional): A callback function to report the progress
                                                    of the connection attempt. Defaults to None.
            retries (int, optional): The number of retries before giving up. Defaults to 3.
            timeout (int, optional): The timeout in seconds for each connection attempt. Defaults to 5.

        Returns:
            str: An error message if the connection fails after all retries, otherwise an empty string
                indicating a successful connection.
        """
        if self.comport is None or self.comport.device == 'test': # FIXME for testing only pylint: disable=fixme
            return ""
        logging_info("Will connect to %s", self.comport.device)
        try:
            # Create the connection
            self.master = mavutil.mavlink_connection(device=self.comport.device, timeout=timeout,
                                                     retries=retries, progress_callback=progress_callback)
            logging_debug("Waiting for MAVLink heartbeat")
            m = self.master.wait_heartbeat(timeout=timeout)
            if m is None:
                logging_error("No MAVLink heartbeat received, connection failed.")
                return "No MAVLink heartbeat received, connection failed."
            self.__target_system = m.get_srcSystem()
            self.__target_component = m.get_srcComponent()
            logging_debug("Connection established with systemID %d, componentID %d.", self.__target_system,
                          self.__target_component)
            logging_info(f"Autopilot type {self.__decode_mav_autopilot(m.autopilot)}")
            if m.autopilot != mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA:
                logging_error("Unsupported autopilot type %s", self.__decode_mav_autopilot(m.autopilot))
                return f"Unsupported autopilot type {self.__decode_mav_autopilot(m.autopilot)}"
            self.vehicle_type = self.__classify_vehicle_type(m.type)
            logging_info(f"Vehicle type {self.__decode_mav_type(m.type)} running {self.vehicle_type} firmware")

            self.__cmd_version()
            m = self.master.recv_match(type='AUTOPILOT_VERSION', blocking=True, timeout=timeout)
            if m is None:
                logging_error("No AUTOPILOT_VERSION MAVLink message received, connection failed.")
                return "No AUTOPILOT_VERSION MAVLink message received, connection failed."
            self.__capabilities = m.capabilities
            _cap_list = self.__decode_flight_capabilities(self.__capabilities)
            # logging_info("Flight Controller Capabilities: %s", (", ").join(
            #     [capability.removeprefix("MAV_PROTOCOL_CAPABILITY_")
            #      for capability in _cap_list]))
            v_major, v_minor, v_patch, v_fw_type = self.__decode_flight_sw_version(m.flight_sw_version)
            self.version = f"{v_major}.{v_minor}.{v_patch}"
            logging_info("Flight Controller Version: %s %s", self.version, v_fw_type)
            # logging_info(f"Flight Controller Middleware version number: {m.middleware_sw_version}")
            # logging_info(f"Flight Controller Operating system version number: {m.os_sw_version}")
            logging_info(f"Flight Controller HW / board version: {m.board_version}")
            # Convert each value in the array to hex and join them together
            flight_custom_version_hex = ''.join(chr(c) for c in m.flight_custom_version)
            # middleware_custom_version_hex = ''.join(chr(c) for c in m.middleware_custom_version)
            os_custom_version_hex = ''.join(chr(c) for c in m.os_custom_version)
            logging_info(f"Flight Controller first 8 hex bytes of the FC git hash: {flight_custom_version_hex}")
            # logging_info(f"Flight Controller first 8 hex bytes of the MW git hash: {middleware_custom_version_hex}")
            logging_info(f"Flight Controller first 8 hex bytes of the ChibiOS git hash: {os_custom_version_hex}")
            if m.vendor_id == 0x1209 and m.product_id == 0x5740:
                return ""  # these are just generic ArduPilot values, there is no value in printing them
            pid_vid_dict = self.__list_ardupilot_supported_usb_pid_vid()
            if m.vendor_id in pid_vid_dict:
                logging_info(f"Flight Controller board vendor: {pid_vid_dict[m.vendor_id]['vendor']}")
                if m.product_id in pid_vid_dict[m.vendor_id]['PID']:
                    logging_info(f"Flight Controller board product: {pid_vid_dict[m.vendor_id]['PID'][m.product_id]}")
                else:
                    logging_info(f"Flight Controller board product ID: 0x{hex(m.product_id)}")
            else:
                logging_info(f"Flight Controller board vendor ID: 0x{hex(m.vendor_id)}")
                logging_info(f"Flight Controller product ID: 0x{hex(m.product_id)}")
            # logging_info(f"Flight Controller UID if provided by hardware: {m.uid}")
        except (ConnectionError, SerialException, PermissionError, ConnectionRefusedError) as e:
            logging_warning("Connection failed: %s", e)
            logging_error("Failed to connect after %d attempts.", retries)
            return str(e)
        return ""

    def download_params(self, progress_callback=None) -> Dict[str, float]:
        """
        Requests all flight controller parameters from a MAVLink connection.

        Returns:
            Dict[str, float]: A dictionary of flight controller parameters.
        """
        # FIXME this entire if statement is for testing only, remove it later pylint: disable=fixme
        if self.master is None and self.comport is not None and self.comport.device == 'test':
            filename = 'params.param'
            logging_warning("Testing active, will load all parameters from the %s file", filename)
            par_dict_with_comments = Par.load_param_file_into_dict(filename)
            return {k: v.value for k, v in par_dict_with_comments.items()}

        if self.master is None:
            return None

        # Check if MAVFTP is supported
        # FIXME remove the "not" once it works pylint: disable=fixme
        if self.__capabilities:
            if not (self.__capabilities & mavutil.mavlink.MAV_PROTOCOL_CAPABILITY_FTP):  # pylint: disable=superfluous-parens
                logging_info("MAVFTP is supported by the %s flight controller", self.comport.device)
                # parameters, _defaults = self.download_params_via_mavftp(progress_callback)
                return {}  # parameters

        logging_info("MAVFTP is not supported by the %s flight controller, fallback to MAVLink", self.comport.device)
        # MAVFTP is not supported, fall back to MAVLink
        return self.__download_params_via_mavlink(progress_callback)

    def __download_params_via_mavlink(self, progress_callback=None) -> Dict[str, float]:
        logging_debug("Will fetch all parameters from the %s flight controller", self.comport.device)
        # Request all parameters
        self.master.mav.param_request_list_send(
            self.master.target_system, self.master.target_component
        )

        # Dictionary to store parameters
        parameters = {}

        # Loop to receive all parameters
        while True:
            try:
                m = self.master.recv_match(type='PARAM_VALUE', blocking=True)
                if m is None:
                    break
                message = m.to_dict()
                param_id = message['param_id'] # .decode("utf-8")
                param_value = message['param_value']
                parameters[param_id] = param_value
                logging_debug('Received parameter: %s = %s', param_id, param_value)
                # Call the progress callback with the current progress
                if progress_callback:
                    progress_callback(len(parameters), m.param_count)
                if m.param_count == len(parameters):
                    logging_debug("Fetched %d parameter values from the %s flight controller",
                                  m.param_count, self.comport.device)
                    break
            except Exception as error:  # pylint: disable=broad-except
                logging_error('Error: %s', error)
                break
        return parameters

    def set_param(self, param_name: str, param_value: float):
        """
        Set a parameter on the flight controller.

        Args:
            param_name (str): The name of the parameter to set.
            param_value (float): The value to set the parameter to.
        """
        if self.master is None: # FIXME for testing only pylint: disable=fixme
            return None
        return self.master.param_set_send(param_name, param_value)

    def reset_and_reconnect(self, reset_progress_callback=None, connection_progress_callback=None, sleep_time: int = None):
        """
        Reset the flight controller and reconnect.

        Args:
            sleep_time (int, optional): The time in seconds to wait before reconnecting.
        """
        if self.master is None: # FIXME for testing only pylint: disable=fixme
            return
        # Issue a reset
        self.master.reboot_autopilot()
        logging_info("Reset command sent to ArduPilot.")
        time_sleep(0.3)

        self.disconnect()

        current_step = 0

        if sleep_time is None or sleep_time <= 7:
            sleep_time = self.__reboot_time

        while current_step != sleep_time:
            # Call the progress callback with the current progress
            if reset_progress_callback:
                reset_progress_callback(current_step, sleep_time)

            # Wait for sleep_time seconds
            time_sleep(1)
            current_step += 1

        # Call the progress callback with the current progress
        if reset_progress_callback:
            reset_progress_callback(current_step, sleep_time)

        # Reconnect to the flight controller
        self.__create_connection_with_retry(connection_progress_callback)

    @staticmethod
    def __list_usb_devices():
        """
        List all connected USB devices.
        """
        ret = []
        return ret # FIXME for testing only pylint: disable=fixme
        # devices = usb.core.find(find_all=True)
        # for device in devices:
        #     try:
        #         manufacturer = usb.util.get_string(device, device.iManufacturer)
        #     except ValueError as e:
        #         logging_warning("Failed to retrieve string descriptor for device (VID:PID) - %04x:%04x: %s",
        #                         device.idVendor, device.idProduct, e)
        #         manufacturer = "Unknown"
        #     try:
        #         product = usb.util.get_string(device, device.iProduct)
        #     except ValueError as e:
        #         logging_warning("Failed to retrieve string descriptor for device (VID:PID) - %04x:%04x: %s",
        #                         device.idVendor, device.idProduct, e)
        #         product = "Unknown"
        #     logging_info("USB device (VID:PID) - %04x:%04x, Manufacturer: %s, Product: %s",
        #                  device.idVendor,
        #                  device.idProduct,
        #                  manufacturer,
        #                  product)
        #     ret.append([device.idVendor,
        #                 device.idProduct,
        #                 manufacturer,
        #                 product])
        # return ret

    @staticmethod
    def __list_serial_ports():
        """
        List all available serial ports.
        """
        comports = serial.tools.list_ports.comports()
        # for port in comports:
        #     logging_debug("ComPort - %s, Description: %s", port.device, port.description)
        return comports

    @staticmethod
    def __list_network_ports():
        """
        List all available network ports.
        """
        return ['tcp:127.0.0.1:5760', 'udp:127.0.0.1:14550']

    def __auto_detect_serial(self):
        for connection in self.__connection_tuples:
            if 'mavlink' in connection[1].lower():
                return [mavutil.SerialPort(device=connection[0], description=connection[1])]

        serial_list = mavutil.auto_detect_serial(preferred_list=preferred_ports)
        serial_list.sort(key=lambda x: x.device)

        # remove OTG2 ports for dual CDC
        if len(serial_list) == 2 and serial_list[0].device.startswith("/dev/serial/by-id"):
            if serial_list[0].device[:-1] == serial_list[1].device[0:-1]:
                serial_list.pop(1)

        return serial_list

    def get_connection_tuples(self):
        """
        Get all available connections.
        """
        return self.__connection_tuples

    @staticmethod
    def __list_ardupilot_supported_usb_pid_vid():
        """
        List all ArduPilot supported USB vendor ID (VID) and product ID (PID).

        source: https://ardupilot.org/dev/docs/USB-IDs.html
        """
        return {
            0x0483: {'vendor': 'ST Microelectronics', 'PID': {0x5740: 'ChibiOS'}},
            0x1209: {'vendor': 'ArduPilot', 'PID': {0x5740: 'MAVLink',
                                                    0x5741: 'Bootloader',
                                                    }
                     },
            0x16D0: {'vendor': 'ArduPilot', 'PID': {0x0E65: 'MAVLink'}},
            0x26AC: {'vendor': '3D Robotics', 'PID': {}},
            0x2DAE: {'vendor': 'Hex', 'PID': {0x1101: 'CubeBlack+',
                                              0x1001: 'CubeBlack bootloader',
                                              0x1011: 'CubeBlack',
                                              0x1016: 'CubeOrange',
                                              0x1005: 'CubePurple bootloader',
                                              0x1015: 'CubePurple',
                                              0x1002: 'CubeYellow bootloader',
                                              0x1012: 'CubeYellow',
                                              0x1003: 'CubeBlue bootloader',
                                              0x1013: 'CubeBlue',              # These where detected by microsoft copilot
                                              0x1004: 'CubeGreen bootloader',
                                              0x1014: 'CubeGreen',
                                              0x1006: 'CubeRed bootloader',
                                              0x1017: 'CubeRed',
                                              0x1007: 'CubeOrange bootloader',
                                              0x1018: 'CubeOrange',
                                              0x1008: 'CubePurple bootloader',
                                              0x1019: 'CubePurple',
                                              }
                     },
            0x3162: {'vendor': 'Holybro', 'PID': {0x004B: 'Durandal'}},
            0x27AC: {'vendor': 'Laser Navigation', 'PID': {0x1151: 'VRBrain-v51',
                                                           0x1152: 'VRBrain-v52',
                                                           0x1154: 'VRBrain-v54',
                                                           0x1910: 'VRCore-v10',
                                                           0x1351: 'VRUBrain-v51',
                                                           }
                     },
        }

    @staticmethod
    def __decode_flight_sw_version(flight_sw_version):
        '''decode 32 bit flight_sw_version mavlink parameter
        corresponds to ArduPilot encoding in  GCS_MAVLINK::send_autopilot_version'''
        fw_type_id = (flight_sw_version >>  0) % 256  # noqa E221, E222
        patch      = (flight_sw_version >>  8) % 256  # noqa E221, E222
        minor      = (flight_sw_version >> 16) % 256  # noqa E221
        major      = (flight_sw_version >> 24) % 256  # noqa E221
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
        '''Decode 32 bit flight controller capabilities bitmask mavlink parameter.
        Returns a list of concise English descriptions of each active capability.
        '''
        # Initialize an empty list to store the descriptions
        descriptions = []

        # Iterate through each bit in the capabilities bitmask
        for bit in range(32):
            # Check if the bit is set
            if capabilities & (1 << bit):
                # Use the bit value to get the corresponding capability enum
                capability = mavutil.mavlink.enums["MAV_PROTOCOL_CAPABILITY"].get(1 << bit, "Unknown capability")
                # Append the description of the capability to the list
                logging_info(capability.description)
                descriptions.append(capability.name)

        return descriptions


    # see for more info:
    # import pymavlink.dialects.v20.ardupilotmega
    # pymavlink.dialects.v20.ardupilotmega.enums["MAV_TYPE"]
    @staticmethod
    def __decode_mav_type(mav_type):
        return mavutil.mavlink.enums["MAV_TYPE"].get(mav_type,
                                                    mavutil.mavlink.EnumEntry("None", "Unknown type")).description


    @staticmethod
    def __decode_mav_autopilot(mav_autopilot):
        return mavutil.mavlink.enums["MAV_AUTOPILOT"].get(mav_autopilot,
                                                        mavutil.mavlink.EnumEntry("None", "Unknown type")).description


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
            mavutil.mavlink.MAV_TYPE_FIXED_WING: 'ArduPlane',
            mavutil.mavlink.MAV_TYPE_QUADROTOR: 'ArduCopter',
            mavutil.mavlink.MAV_TYPE_COAXIAL: 'Heli',
            mavutil.mavlink.MAV_TYPE_HELICOPTER: 'Heli',
            mavutil.mavlink.MAV_TYPE_ANTENNA_TRACKER: 'AntennaTracker',
            mavutil.mavlink.MAV_TYPE_GCS: 'AP_Periph',
            mavutil.mavlink.MAV_TYPE_AIRSHIP: 'ArduBlimp',
            mavutil.mavlink.MAV_TYPE_FREE_BALLOON: 'ArduBlimp',
            mavutil.mavlink.MAV_TYPE_ROCKET: 'ArduCopter',
            mavutil.mavlink.MAV_TYPE_GROUND_ROVER: 'Rover',
            mavutil.mavlink.MAV_TYPE_SURFACE_BOAT: 'Rover',
            mavutil.mavlink.MAV_TYPE_SUBMARINE: 'ArduSub',
            mavutil.mavlink.MAV_TYPE_HEXAROTOR: 'ArduCopter',
            mavutil.mavlink.MAV_TYPE_OCTOROTOR: 'ArduCopter',
            mavutil.mavlink.MAV_TYPE_TRICOPTER: 'ArduCopter',
            mavutil.mavlink.MAV_TYPE_FLAPPING_WING: 'ArduPlane',
            mavutil.mavlink.MAV_TYPE_KITE: 'ArduPlane',
            mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER: 'AP_Periph',
            mavutil.mavlink.MAV_TYPE_VTOL_DUOROTOR: 'ArduPlane',
            mavutil.mavlink.MAV_TYPE_VTOL_QUADROTOR: 'ArduPlane',
            mavutil.mavlink.MAV_TYPE_VTOL_TILTROTOR: 'ArduPlane',
            mavutil.mavlink.MAV_TYPE_VTOL_RESERVED2: 'ArduPlane',
            mavutil.mavlink.MAV_TYPE_VTOL_RESERVED3: 'ArduPlane',
            mavutil.mavlink.MAV_TYPE_VTOL_RESERVED4: 'ArduPlane',
            mavutil.mavlink.MAV_TYPE_VTOL_RESERVED5: 'ArduPlane',
            mavutil.mavlink.MAV_TYPE_GIMBAL: 'AP_Periph',
            mavutil.mavlink.MAV_TYPE_ADSB: 'AP_Periph',
            mavutil.mavlink.MAV_TYPE_PARAFOIL: 'ArduPlane',
            mavutil.mavlink.MAV_TYPE_DODECAROTOR: 'ArduCopter',
            mavutil.mavlink.MAV_TYPE_CAMERA: 'AP_Periph',
            mavutil.mavlink.MAV_TYPE_CHARGING_STATION: 'AP_Periph',
            mavutil.mavlink.MAV_TYPE_FLARM: 'AP_Periph',
            mavutil.mavlink.MAV_TYPE_SERVO: 'AP_Periph',
            mavutil.mavlink.MAV_TYPE_ODID: 'AP_Periph',
            mavutil.mavlink.MAV_TYPE_DECAROTOR: 'ArduCopter',
            mavutil.mavlink.MAV_TYPE_BATTERY: 'AP_Periph',
            mavutil.mavlink.MAV_TYPE_PARACHUTE: 'AP_Periph',
            mavutil.mavlink.MAV_TYPE_LOG: 'AP_Periph',
            mavutil.mavlink.MAV_TYPE_OSD: 'AP_Periph',
            mavutil.mavlink.MAV_TYPE_IMU: 'AP_Periph',
            mavutil.mavlink.MAV_TYPE_GPS: 'AP_Periph',
            mavutil.mavlink.MAV_TYPE_WINCH: 'AP_Periph',
            # Add more mappings as needed
        }

        # Return the classified vehicle type based on the MAV_TYPE enum
        return mav_type_to_vehicle_type.get(mav_type_int, None)

    @staticmethod
    def add_argparse_arguments(parser):
        parser.add_argument('--device',
                            type=str,
                            default="",
                            help='MAVLink connection string to the flight controller. If set to "none" no connection is made.'
                            ' Defaults to autodetection'
                            )
        parser.add_argument('-r', '--reboot-time',
                            type=int,
                            default=7,
                            help='Flight controller reboot time. '
                            'Default is %(default)s')
        return parser
