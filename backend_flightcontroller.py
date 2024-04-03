#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

AP_FLAKE8_CLEAN

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
from annotate_params import Par

# adding all this allows pyinstaller to build a working windows executable
# note that using --hidden-import does not work for these modules
try:
    from pymavlink import mavutil
except Exception:
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
    def __init__(self, device: str):
        self.device = device

    def read(self, _len):
        return ""

    def write(self, _buf):
        raise Exception("write always fails")

    def inWaiting(self):
        return 0

    def close(self):
        pass


class FlightController:
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

        self.reboot_time = reboot_time
        comports = FlightController.list_serial_ports()
        # ubcports = FlightController.list_usb_devices()
        netports = FlightController.list_network_ports()
        # list of tuples with the first element being the port name and the second element being the port description
        self.connection_tuples = [(port.device, port.description) for port in comports] + [(port, port) for port in netports]
        logging_info('Available connection ports are:')
        for port in self.connection_tuples:
            logging_info("%s - %s", port[0], port[1])
        self.connection_tuples += [tuple(['Add another', 'Add another'])]  # now that is is logged, add the 'Add another' tuple
        self.master = None
        self.comport = None
        self.fc_parameters = {}

    def add_connection(self, connection_string: str):
        """
        Add a new connection to the list of available connections.
        """
        if connection_string:
            # Check if connection_string is not the first element of any tuple in self.other_connection_tuples
            if all(connection_string != t[0] for t in self.connection_tuples):
                self.connection_tuples.insert(-1, (connection_string, connection_string))
                logging_debug("Added connection %s", connection_string)
                return True
            logging_debug("Did not add duplicated connection %s", connection_string)
        else:
            logging_debug("Did not add empty connection")
        return False

    def connect(self, device: str, progress_callback=None):
        """
        Connect to the FlightController with a connection string.

        Args:
            device (str): The connection string to the flight controller.
        """
        if device:
            self.add_connection(device)
            self.comport = mavutil.SerialPort(device=device, description=device)
        else:
            autodetect_serial = self.auto_detect_serial()
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
                    # Add the detected serial port to the list of available connections because it is not there
                    if self.comport.device not in [t[0] for t in self.connection_tuples]:
                        self.connection_tuples.insert(-1, (self.comport.device, self.comport.description))
            else:
                return "No serial ports found. Please connect a flight controller and try again."
        error_message = self.create_connection_with_retry(progress_callback=progress_callback)
        if device == 'test': # FIXME for testing only
            self.fc_parameters['INS_LOG_BAT_MASK'] = 1.0
            self.fc_parameters['INS_TCAL1_TMAX'] = 1.0
            self.fc_parameters['COMPASS_DEV_ID'] = 1.0
        return error_message

    def create_connection_with_retry(self, progress_callback, retries: int = 3,
                                     timeout: int = 5) -> mavutil.mavlink_connection:
        """
        Attempt to create a connection to the flight controller with retries.

        Args:
            retries (int, optional): The number of retries before giving up. Defaults to 3.
            timeout (int, optional): The timeout in seconds for each connection attempt. Defaults to 5.

        Returns:
            mavutil.mavlink_connection: The MAVLink connection object if successful, None otherwise.
        """
        if self.comport is None or self.comport.device == 'test': # FIXME for testing only
            return None
        logging_info("Will connect to %s", self.comport.device)
        try:
            # Create the connection
            self.master = mavutil.mavlink_connection(device=self.comport.device, timeout=timeout,
                                                     retries=retries, progress_callback=progress_callback)
            logging_debug("Waiting for heartbeat")
            self.master.wait_heartbeat(timeout=timeout)
            logging_debug("Connection established.")
        except (ConnectionError, SerialException, PermissionError, ConnectionRefusedError) as e:
            logging_warning("Connection failed: %s", e)
            logging_error("Failed to connect after %d attempts.", retries)
            return e
        return ""

    def read_params(self, progress_callback=None) -> Dict[str, float]:
        """
        Requests all flight controller parameters from a MAVLink connection.

        Returns:
            Dict[str, float]: A dictionary of flight controller parameters.
        """
        if self.master is None: # FIXME for testing only
            filename = os_path.join('4.4.4-test-params', '00_default.param')
            logging_warning("Testing active, will load all parameters from the %s file", filename)
            par_dict_with_comments = Par.load_param_file_into_dict(filename)
            return {k: v.value for k, v in par_dict_with_comments.items()}

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
            except Exception as error:
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
        if self.master is None: # FIXME for testing only
            return None
        return self.master.param_set_send(param_name, param_value)

    def reset_and_reconnect(self, reset_progress_callback=None, connection_progress_callback=None, sleep_time: int = None):
        """
        Reset the flight controller and reconnect.

        Args:
            sleep_time (int, optional): The time in seconds to wait before reconnecting.
        """
        if self.master is None: # FIXME for testing only
            return None
        # Issue a reset
        self.master.reboot_autopilot()
        logging_info("Reset command sent to ArduPilot.")
        time_sleep(0.3)

        self.close_connection()

        current_step = 0

        if sleep_time is None or sleep_time <= 7:
            sleep_time = self.reboot_time

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
        self.create_connection_with_retry(connection_progress_callback)

    def close_connection(self):
        """
        Close the connection to the flight controller.
        """
        if self.master is not None:
            self.master.close()
            self.master = None
        self.fc_parameters = {}

    @staticmethod
    def list_usb_devices():
        """
        List all connected USB devices.
        """
        ret = []
        return ret # FIXME for testing only
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
    def list_serial_ports():
        """
        List all available serial ports.
        """
        comports = serial.tools.list_ports.comports()
        # for port in comports:
        #     logging_debug("ComPort - %s, Description: %s", port.device, port.description)
        return comports

    @staticmethod
    def list_network_ports():
        """
        List all available network ports.
        """
        return ['tcp:127.0.0.1:5760', 'udp:127.0.0.1:14550']

    @staticmethod
    def auto_detect_serial():
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
        return self.connection_tuples

    @staticmethod
    def list_ardupilot_supported_usb_pid_vid():
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
