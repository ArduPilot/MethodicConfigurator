"""
Flight controller interface.

This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from argparse import ArgumentParser
from logging import debug as logging_debug
from logging import error as logging_error
from logging import info as logging_info
from logging import warning as logging_warning
from os import name as os_name
from os import path as os_path
from os import readlink as os_readlink
from time import sleep as time_sleep
from time import time as time_time
from typing import Callable, NoReturn, Optional, Union

import serial.tools.list_ports
import serial.tools.list_ports_common
from pymavlink import mavutil
from pymavlink.dialects.v20.ardupilotmega import MAVLink_autopilot_version_message
from serial.serialutil import SerialException

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.annotate_params import Par
from ardupilot_methodic_configurator.argparse_check_range import CheckRange
from ardupilot_methodic_configurator.backend_flightcontroller_info import BackendFlightcontrollerInfo
from ardupilot_methodic_configurator.backend_mavftp import MAVFTP


class FakeSerialForTests:
    """
    A mock serial class for unit testing purposes.

    This class simulates the behavior of a serial connection for testing purposes,
    allowing for the testing of serial communication without needing a physical
    serial device. It includes methods for reading, writing, and checking the
    number of bytes in the input buffer, as well as closing the connection.
    """

    def __init__(self, device: str) -> None:
        self.device = device

    def read(self, _len) -> str:  # noqa: ANN001
        return ""

    def write(self, _buf) -> NoReturn:  # noqa: ANN001
        msg = "write always fails"
        raise Exception(msg)  # pylint: disable=broad-exception-raised

    def inWaiting(self) -> int:  # noqa: N802, pylint: disable=invalid-name
        return 0

    def close(self) -> None:
        pass


DEFAULT_BAUDRATE: int = 115200
DEFAULT_REBOOT_TIME: int = 7


class FlightController:
    """
    A class to manage the connection and parameters of a flight controller.

    Attributes:
        device (str): The connection string to the flight controller.
        master (mavutil.mavlink_connection): The MAVLink connection object.
        fc_parameters (Dict[str, float]): A dictionary of flight controller parameters.

    """

    def __init__(self, reboot_time: int = DEFAULT_REBOOT_TIME, baudrate: int = DEFAULT_BAUDRATE) -> None:
        """Initialize the FlightController communication object."""
        # warn people about ModemManager which interferes badly with ArduPilot
        if os_path.exists("/usr/sbin/ModemManager"):
            logging_warning(_("You should uninstall ModemManager as it conflicts with ArduPilot"))

        self.__reboot_time = reboot_time
        self.__baudrate = baudrate
        self.__connection_tuples: list[tuple[str, str]] = []
        self.discover_connections()
        self.master: Union[mavutil.mavlink_connection, None] = None  # pyright: ignore[reportGeneralTypeIssues]
        self.comport: Union[mavutil.SerialPort, None] = None
        self.fc_parameters: dict[str, float] = {}
        self.info = BackendFlightcontrollerInfo()

    def discover_connections(self) -> None:
        comports = FlightController.__list_serial_ports()
        netports = FlightController.__list_network_ports()
        # list of tuples with the first element being the port name and the second element being the port description
        self.__connection_tuples = [(port.device, port.description) for port in comports] + [(port, port) for port in netports]
        logging_info(_("Available connection ports are:"))
        for port in self.__connection_tuples:
            logging_info("%s - %s", port[0], port[1])
        # now that it is logged, add the 'Add another' tuple
        self.__connection_tuples += [(_("Add another"), _("Add another"))]

    def disconnect(self) -> None:
        """Close the connection to the flight controller."""
        if self.master is not None:
            self.master.close()
            self.master = None
        self.fc_parameters = {}
        self.info = BackendFlightcontrollerInfo()

    def add_connection(self, connection_string: str) -> bool:
        """Add a new connection to the list of available connections."""
        if connection_string:
            # Check if connection_string is not the first element of any tuple in self.other_connection_tuples
            if all(connection_string != t[0] for t in self.__connection_tuples):
                self.__connection_tuples.insert(-1, (connection_string, connection_string))
                logging_debug(_("Added connection %s"), connection_string)
                return True
            logging_debug(_("Did not add duplicated connection %s"), connection_string)
        else:
            logging_debug(_("Did not add empty connection"))
        return False

    def connect(
        self, device: str, progress_callback: Union[None, Callable[[int, int], None]] = None, log_errors: bool = True
    ) -> str:
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
                                                    of the connection attempt. Default is None.
            log_errors: log errors

        Returns:
            str: An error message if the connection fails, otherwise an empty string indicating
                a successful connection.

        """
        if device:
            if device == "none":
                return ""
            self.add_connection(device)
            self.comport = mavutil.SerialPort(device=device, description=device)
        else:
            autodetect_serial = self.__auto_detect_serial()
            if autodetect_serial:
                # Resolve the soft link if it's a Linux system
                if os_name == "posix":
                    try:
                        dev = autodetect_serial[0].device
                        logging_debug(_("Auto-detected device %s"), dev)
                        # Get the directory part of the soft link
                        softlink_dir = os_path.dirname(dev)
                        # Resolve the soft link and join it with the directory part
                        resolved_path = os_path.abspath(os_path.join(softlink_dir, os_readlink(dev)))
                        autodetect_serial[0].device = resolved_path
                        logging_debug(_("Resolved soft link %s to %s"), dev, resolved_path)
                    except OSError:
                        pass  # Not a soft link, proceed with the original device path
                self.comport = autodetect_serial[0]
                # Add the detected serial port to the list of available connections if it is not there
                if self.comport and self.comport.device not in [t[0] for t in self.__connection_tuples]:
                    self.__connection_tuples.insert(-1, (self.comport.device, getattr(self.comport, "description", "")))
            else:
                return _("No serial ports found. Please connect a flight controller and try again.")
        return self.__create_connection_with_retry(
            progress_callback=progress_callback, baudrate=self.__baudrate, log_errors=log_errors
        )

    def __request_banner(self) -> None:
        """Request banner information from the flight controller."""
        # https://mavlink.io/en/messages/ardupilotmega.html#MAV_CMD_DO_SEND_BANNER
        if self.master is not None:
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_DO_SEND_BANNER,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
            )

    def __receive_banner_text(self) -> list[str]:
        """Starts listening for STATUS_TEXT MAVLink messages."""
        start_time = time_time()
        banner_msgs: list[str] = []
        while self.master:
            msg = self.master.recv_match(type="STATUSTEXT", blocking=False)
            if msg:
                if banner_msgs:
                    banner_msgs.append(msg.text)
                else:
                    banner_msgs = [msg.text]
            time_sleep(0.1)  # Sleep briefly to reduce CPU usage
            if time_time() - start_time > 1:  # Check if 1 seconds have passed since the start of the loop
                break  # Exit the loop if 1 seconds have elapsed
        return banner_msgs

    def __request_message(self, message_id: int) -> None:
        if self.master is not None:
            self.master.mav.command_long_send(
                self.info.system_id,
                self.info.component_id,
                mavutil.mavlink.MAV_CMD_REQUEST_MESSAGE,
                0,  # confirmation
                message_id,
                0,
                0,
                0,
                0,
                0,
                0,
            )

    def __create_connection_with_retry(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        progress_callback: Union[None, Callable[[int, int], None]],
        retries: int = 3,
        timeout: int = 5,
        baudrate: int = DEFAULT_BAUDRATE,
        log_errors: bool = True,
    ) -> str:
        """
        Attempts to create a connection to the flight controller with retries.

        This method attempts to establish a connection to the flight controller using the
        provided device connection string. It will retry the connection attempt up to the
        specified number of retries if the initial attempt fails. The method also supports
        a progress callback to report the progress of the connection attempt.

        Args:
            progress_callback (callable, optional): A callback function to report the progress
                                                    of the connection attempt. Default is None.
            retries (int, optional): The number of retries before giving up. Default is 3.
            timeout (int, optional): The timeout in seconds for each connection attempt. Default is 5.
            baudrate (int, optional): The baud rate for the connection. Default is DEFAULT_BAUDRATE.
            log_errors (bool): log errors.

        Returns:
            str: An error message if the connection fails after all retries, otherwise an empty string
                indicating a successful connection.

        """
        if self.comport is None or self.comport.device == "test":  # FIXME for testing only pylint: disable=fixme
            return ""
        logging_info(_("Will connect to %s @ %u baud"), self.comport.device, baudrate)
        try:
            # Create the connection
            self.master = mavutil.mavlink_connection(
                device=self.comport.device,
                baud=baudrate,
                timeout=timeout,
                retries=retries,
                progress_callback=progress_callback,
            )
            logging_debug(_("Waiting for MAVLink heartbeat"))
            if not self.master:
                msg = f"Failed to create mavlink connect to {self.comport.device}"
                raise ConnectionError(msg)
            m = self.master.wait_heartbeat(timeout=timeout)
            if m is None:
                return _("No MAVLink heartbeat received, connection failed.")
            self.info.set_system_id_and_component_id(m.get_srcSystem(), m.get_srcComponent())
            logging_debug(
                _("Connection established with systemID %d, componentID %d."), self.info.system_id, self.info.component_id
            )

            self.info.set_autopilot(m.autopilot)
            if self.info.is_supported:
                msg = _("Autopilot type {self.info.autopilot}")
                logging_info(msg.format(**locals()))
            else:
                msg = _("Unsupported autopilot type {self.info.autopilot}")
                return msg.format(**locals())

            self.info.set_type(m.type)
            msg = _("Vehicle type: {self.info.mav_type} running {self.info.vehicle_type} firmware")
            logging_info(msg.format(**locals()))

            self.__request_banner()
            banner_msgs = self.__receive_banner_text()

            self.__request_message(mavutil.mavlink.MAVLINK_MSG_ID_AUTOPILOT_VERSION)
            m = self.master.recv_match(type="AUTOPILOT_VERSION", blocking=True, timeout=timeout)
            return self.__process_autopilot_version(m, banner_msgs)
        except (ConnectionError, SerialException, PermissionError, ConnectionRefusedError) as e:
            if log_errors:
                logging_warning(_("Connection failed: %s"), e)
                logging_error(_("Failed to connect after %d attempts."), retries)
            error_message = str(e)
            guidance = self.__get_connection_error_guidance(e, self.comport.device if self.comport else "")
            if guidance:
                error_message = f"{error_message}\n\n{guidance}"
            return error_message

    def __get_connection_error_guidance(self, error: Exception, device: str) -> str:
        """
        Provides guidance based on the type of connection error.

        Args:
            error (Exception): The exception that occurred during connection.
            device (str): The device path or connection string.

        Returns:
            str: Guidance message specific to the error type, or empty string if no specific guidance.

        """
        # Check for permission denied errors on Linux
        if isinstance(error, PermissionError) and os_name == "posix" and "/dev/" in device:
            return _(
                "Permission denied accessing the serial port. This is common on Linux systems.\n"
                "To fix this issue, add your user to the 'dialout' group with the following command:\n"
                "    sudo adduser $USER dialout\n"
                "Then log out and log back in for the changes to take effect."
            )

        # Add more specific guidance for other error types as needed

        return ""

    def __process_autopilot_version(self, m: MAVLink_autopilot_version_message, banner_msgs: list[str]) -> str:
        if m is None:
            return _(
                "No AUTOPILOT_VERSION MAVLink message received, connection failed.\n"
                "Only ArduPilot versions newer than 4.3.8 are supported.\n"
                "Make sure parameter SERIAL0_PROTOCOL is set to 2"
            )
        self.info.set_capabilities(m.capabilities)
        self.info.set_flight_sw_version(m.flight_sw_version)
        self.info.set_usb_vendor_and_product_ids(m.vendor_id, m.product_id)  # must be done before set_board_version()
        self.info.set_board_version(m.board_version)
        self.info.set_flight_custom_version(m.flight_custom_version)
        self.info.set_os_custom_version(m.os_custom_version)

        os_custom_version = ""
        os_custom_version_index = None
        for i, msg in enumerate(banner_msgs):
            if "ChibiOS:" in msg:
                os_custom_version = msg.split(" ")[1].strip()
                hash_len1 = max(7, len(os_custom_version) - 1)
                hash_len2 = max(7, len(self.info.os_custom_version) - 1)
                hash_len = min(hash_len1, hash_len2)
                if os_custom_version[:hash_len] != self.info.os_custom_version[:hash_len]:
                    logging_warning(
                        _("ChibiOS version mismatch: %s (BANNER) != % s (AUTOPILOT_VERSION)"),
                        os_custom_version,
                        self.info.os_custom_version,
                    )
                os_custom_version_index = i
                continue
            logging_debug("FC banner %s", msg)

        # the banner message after the ChibiOS one contains the FC type
        firmware_type = ""
        if os_custom_version_index is not None and os_custom_version_index + 1 < len(banner_msgs):
            firmware_type_banner_substrings = banner_msgs[os_custom_version_index + 1].split(" ")
            if len(firmware_type_banner_substrings) >= 3:
                firmware_type = firmware_type_banner_substrings[0]
        if firmware_type and firmware_type != self.info.firmware_type:
            logging_debug(
                _("FC firmware type mismatch: %s (BANNER) != %s (AUTOPILOT_VERSION)"), firmware_type, self.info.firmware_type
            )
            self.info.firmware_type = firmware_type  # force the one from the banner because it is more reliable
        return ""

    def download_params(
        self, progress_callback: Union[None, Callable[[int, int], None]] = None
    ) -> tuple[dict[str, float], dict[str, "Par"]]:
        """
        Requests all flight controller parameters from a MAVLink connection.

        Returns:
            Dict[str, float]: A dictionary of flight controller parameters.
            Dict[str, Par]: A dictionary of flight controller default parameters.

        """
        # FIXME this entire if statement is for testing only, remove it later pylint: disable=fixme
        if self.master is None and self.comport is not None and self.comport.device == "test":
            filename = "params.param"
            logging_warning(_("Testing active, will load all parameters from the %s file"), filename)
            par_dict_with_comments = Par.load_param_file_into_dict(filename)
            return {k: v.value for k, v in par_dict_with_comments.items()}, {}

        if self.master is None:
            return {}, {}

        # Check if MAVFTP is supported
        comport_device = getattr(self.comport, "device", "")
        if self.info.is_mavftp_supported:
            logging_info(_("MAVFTP is supported by the %s flight controller"), comport_device)

            param_dict, default_param_dict = self.download_params_via_mavftp(progress_callback)
            if param_dict:
                return param_dict, default_param_dict

        logging_info(_("MAVFTP is not supported by the %s flight controller, fallback to MAVLink"), comport_device)
        return self.__download_params_via_mavlink(progress_callback), {}

    def __download_params_via_mavlink(
        self, progress_callback: Union[None, Callable[[int, int], None]] = None
    ) -> dict[str, float]:
        comport_device = getattr(self.comport, "device", "")
        logging_debug(_("Will fetch all parameters from the %s flight controller"), comport_device)

        # Dictionary to store parameters
        parameters: dict[str, float] = {}

        # Request all parameters
        if self.master is None:
            return parameters

        self.master.mav.param_request_list_send(self.master.target_system, self.master.target_component)

        # Loop to receive all parameters
        while True:
            try:
                m = self.master.recv_match(type="PARAM_VALUE", blocking=True, timeout=10)
                if m is None:
                    break
                message = m.to_dict()
                param_id = message["param_id"]  # .decode("utf-8")
                param_value = message["param_value"]
                parameters[param_id] = param_value
                logging_debug(_("Received parameter: %s = %s"), param_id, param_value)
                # Call the progress callback with the current progress
                if progress_callback:
                    progress_callback(len(parameters), m.param_count)
                if m.param_count == len(parameters):
                    logging_debug(
                        _("Fetched %d parameter values from the %s flight controller"), m.param_count, comport_device
                    )
                    break
            except Exception as error:  # pylint: disable=broad-except
                logging_error(_("Error: %s"), error)
                break
        return parameters

    def download_params_via_mavftp(
        self, progress_callback: Union[None, Callable[[int, int], None]] = None
    ) -> tuple[dict[str, float], dict[str, "Par"]]:
        if self.master is None:
            return {}, {}
        mavftp = MAVFTP(self.master, target_system=self.master.target_system, target_component=self.master.target_component)

        def get_params_progress_callback(completion: float) -> None:
            if progress_callback is not None and completion is not None:
                progress_callback(int(completion * 100), 100)

        complete_param_filename = "complete.param"
        default_param_filename = "00_default.param"
        mavftp.cmd_getparams([complete_param_filename, default_param_filename], progress_callback=get_params_progress_callback)
        ret = mavftp.process_ftp_reply("getparams", timeout=10)
        pdict = {}
        if ret.error_code == 0:
            # load the parameters from the file
            par_dict = Par.load_param_file_into_dict(complete_param_filename)
            for name, data in par_dict.items():
                pdict[name] = data.value
            defdict = Par.load_param_file_into_dict(default_param_filename)
        else:
            ret.display_message()
            defdict = {}

        return pdict, defdict

    def set_param(self, param_name: str, param_value: float) -> None:
        """
        Set a parameter on the flight controller.

        Args:
            param_name (str): The name of the parameter to set.
            param_value (float): The value to set the parameter to.

        """
        if self.master is None:  # FIXME for testing only pylint: disable=fixme
            return
        self.master.param_set_send(param_name, param_value)

    def reset_and_reconnect(
        self,
        reset_progress_callback: Union[None, Callable[[int, int], None]] = None,
        connection_progress_callback: Union[None, Callable[[int, int], None]] = None,
        extra_sleep_time: Optional[int] = None,
    ) -> str:
        """
        Reset the flight controller and reconnect.

        Args:
            reset_progress_callback: reset callback function
            connection_progress_callback: connection callback function
            extra_sleep_time (int, optional): The time in seconds to wait before reconnecting.

        """
        if self.master is None:  # FIXME for testing only pylint: disable=fixme
            return ""
        # Issue a reset
        self.master.reboot_autopilot()
        logging_info(_("Reset command sent to ArduPilot."))
        time_sleep(0.3)

        self.disconnect()

        current_step = 0

        if extra_sleep_time is None or extra_sleep_time < 0:
            extra_sleep_time = 0

        sleep_time = self.__reboot_time + extra_sleep_time

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
        return self.__create_connection_with_retry(connection_progress_callback, baudrate=self.__baudrate)

    @staticmethod
    def __list_serial_ports() -> list[serial.tools.list_ports_common.ListPortInfo]:
        """List all available serial ports."""
        comports = serial.tools.list_ports.comports()
        for port in comports:
            logging_debug("ComPort - %s, Description: %s", port.device, port.description)
        return comports  # type: ignore[no-any-return]

    # Motor Test Functionality

    def test_motor(self, motor_number: int, throttle_percent: int, timeout_seconds: int) -> tuple[bool, str]:
        """
        Test a specific motor.

        Args:
            motor_number: Motor number (1-based, as used by ArduPilot)
            throttle_percent: Throttle percentage (0-100)
            timeout_seconds: Test duration in seconds

        Returns:
            tuple[bool, str]: (success, error_message) - success is True if command was sent successfully,
                             error_message is empty string on success or contains error description on failure

        """
        if self.master is None:
            error_msg = _("No flight controller connection available for motor test")
            logging_error(error_msg)
            return False, error_msg

        try:
            # MAV_CMD_DO_MOTOR_TEST command
            # https://mavlink.io/en/messages/common.html#MAV_CMD_DO_MOTOR_TEST
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
                0,  # confirmation
                motor_number,  # param1: motor number
                mavutil.mavlink.MOTOR_TEST_THROTTLE_PERCENT,  # param2: throttle type
                throttle_percent,  # param3: throttle value
                timeout_seconds,  # param4: timeout
                motor_number,  # param5: motor count (same as motor number for single motor test)
                mavutil.mavlink.MOTOR_TEST_ORDER_BOARD,  # param6: test order
                0,  # param7: unused
            )
            logging_info(
                _("Motor test command sent: Motor %(motor)d at %(throttle)d%% for %(duration)d seconds"),
                {
                    "motor": motor_number,
                    "throttle": throttle_percent,
                    "duration": timeout_seconds,
                },
            )
            return True, ""

        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = _("Failed to send motor test command: %(error)s") % {"error": str(e)}
            logging_error(error_msg)
            return False, error_msg

    def test_all_motors(self, throttle_percent: int, timeout_seconds: int) -> tuple[bool, str]:
        """
        Test all motors simultaneously.

        Args:
            throttle_percent: Throttle percentage (0-100)
            timeout_seconds: Test duration in seconds

        Returns:
            tuple[bool, str]: (success, error_message) - success is True if command was sent successfully,
                             error_message is empty string on success or contains error description on failure

        """
        if self.master is None:
            error_msg = _("No flight controller connection available for motor test")
            logging_error(error_msg)
            return False, error_msg

        try:
            # MAV_CMD_DO_MOTOR_TEST command for all motors
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
                0,  # confirmation
                0,  # param1: motor count (all motors)
                mavutil.mavlink.MOTOR_TEST_THROTTLE_PERCENT,  # param2: throttle type
                throttle_percent,  # param3: throttle value
                timeout_seconds,  # param4: timeout
                0,  # param5: motor count
                mavutil.mavlink.MOTOR_TEST_ORDER_BOARD,  # param6: test order
                0,  # param7: unused
            )
            logging_info(
                _("All motors test command sent at %(throttle)d%% for %(duration)d seconds"),
                {
                    "throttle": throttle_percent,
                    "duration": timeout_seconds,
                },
            )
            return True, ""

        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = _("Failed to send all motors test command: %(error)s") % {"error": str(e)}
            logging_error(error_msg)
            return False, error_msg

    def test_motors_in_sequence(self, motor_number: int, throttle_percent: int, timeout_seconds: int) -> tuple[bool, str]:
        """
        Test motors in sequence (A, B, C, D, etc.).

        Args:
            motor_number: The motor number to test (1-based index)
            throttle_percent: Throttle percentage (1-100)
            timeout_seconds: Test duration per motor in seconds

        Returns:
            tuple[bool, str]: (success, error_message) - success is True if command was sent successfully,
                             error_message is empty string on success or contains error description on failure

        """
        if self.master is None:
            error_msg = _("No flight controller connection available for motor test")
            logging_error(error_msg)
            return False, error_msg

        try:
            # MAV_CMD_DO_MOTOR_TEST command for sequence test
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
                0,  # confirmation
                motor_number,  # param1: motor count
                mavutil.mavlink.MOTOR_TEST_THROTTLE_PERCENT,  # param2: throttle type
                throttle_percent,  # param3: throttle value
                timeout_seconds,  # param4: timeout per motor
                motor_number,  # param5: motor count
                mavutil.mavlink.MOTOR_TEST_ORDER_SEQUENCE,  # param6: test order (sequence)
                0,  # param7: unused
            )
            logging_info(
                _("Sequential motor test command sent at %(throttle)d%% for %(duration)d seconds per motor"),
                {
                    "throttle": throttle_percent,
                    "duration": timeout_seconds,
                },
            )
            return True, ""

        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = _("Failed to send sequential motor test command: %(error)s") % {"error": str(e)}
            logging_error(error_msg)
            return False, error_msg

    def stop_all_motors(self) -> tuple[bool, str]:
        """
        Emergency stop for all motors.

        Returns:
            tuple[bool, str]: (success, error_message) - success is True if command was sent successfully,
                             error_message is empty string on success or contains error description on failure

        """
        if self.master is None:
            error_msg = _("No flight controller connection available for motor stop")
            logging_error(error_msg)
            return False, error_msg

        try:
            # Send motor test command with 0% throttle to stop all motors
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
                0,  # confirmation
                0,  # param1: motor number (0 = all motors)
                mavutil.mavlink.MOTOR_TEST_THROTTLE_PERCENT,  # param2: throttle type
                0,  # param3: throttle value (0% = stop)
                0,  # param4: timeout (0 = immediate stop)
                0,  # param5: motor count
                mavutil.mavlink.MOTOR_TEST_ORDER_BOARD,  # param6: test order
                0,  # param7: unused
            )
            logging_info(_("Motor stop command sent"))
            return True, ""

        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = _("Failed to send motor stop command: %(error)s") % {"error": str(e)}
            logging_error(error_msg)
            return False, error_msg

    def request_periodic_battery_status(self, interval_microseconds: int = 1000000) -> bool:
        """
        Request periodic BATTERY_STATUS messages from the flight controller.

        Args:
            interval_microseconds: Message interval in microseconds (default: 1 second = 1,000,000 microseconds)

        Returns:
            bool: True if request was sent successfully, False otherwise

        """
        if self.master is None:
            logging_debug(_("No flight controller connection available for battery status request"))
            return False

        try:
            # MAV_CMD_SET_MESSAGE_INTERVAL command to request periodic BATTERY_STATUS messages
            # https://mavlink.io/en/messages/common.html#MAV_CMD_SET_MESSAGE_INTERVAL
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                0,  # confirmation
                mavutil.mavlink.MAVLINK_MSG_ID_BATTERY_STATUS,  # param1: message ID (BATTERY_STATUS)
                interval_microseconds,  # param2: interval in microseconds
                0,  # param3: unused
                0,  # param4: unused
                0,  # param5: unused
                0,  # param6: unused
                0,  # param7: unused
            )
            logging_debug(
                _("Requested periodic BATTERY_STATUS messages every %(interval)d microseconds"),
                {"interval": interval_microseconds},
            )
            return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_debug(_("Failed to request periodic battery status: %(error)s"), {"error": str(e)})
            return False

    def get_battery_status(self) -> tuple[Union[tuple[float, float], None], str]:
        """
        Get current battery voltage and current.

        Returns:
            tuple[Union[tuple[float, float], None], str]: ((voltage, current), error_message) -
                                                         voltage and current in volts and amps,
                                                         or None if not available with error message

        """
        if not self.fc_parameters or self.master is None:
            error_msg = _("No flight controller connection or parameters available")
            return None, error_msg

        # Check if battery monitoring is enabled
        if not self.is_battery_monitoring_enabled():
            error_msg = _("Battery monitoring is not enabled (BATT_MONITOR=0)")
            return None, error_msg

        try:
            # Try to get real telemetry data
            battery_status = self.master.recv_match(type="BATTERY_STATUS", blocking=True, timeout=2)
            if battery_status:
                # Convert from millivolts to volts, and centiamps to amps
                voltage = battery_status.voltages[0] / 1000.0 if battery_status.voltages[0] != -1 else 0.0
                current = battery_status.current_battery / 100.0 if battery_status.current_battery != -1 else 0.0
                return (voltage, current), ""
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_debug(_("Failed to get battery status from telemetry: %(error)s"), {"error": str(e)})

        error_msg = _("Battery status not available from telemetry")
        return None, error_msg

    def get_voltage_thresholds(self) -> tuple[float, float]:
        """
        Get battery voltage thresholds for motor testing safety.

        Returns:
            tuple[float, float]: (min_voltage, max_voltage) for safe motor testing

        """
        min_voltage = self.fc_parameters.get("BATT_ARM_VOLT", 0.0)
        max_voltage = self.fc_parameters.get("MOT_BAT_VOLT_MAX", 0.0)
        return (min_voltage, max_voltage)

    def is_battery_monitoring_enabled(self) -> bool:
        """
        Check if battery monitoring is enabled.

        Returns:
            bool: True if BATT_MONITOR != 0, False otherwise

        """
        return self.fc_parameters.get("BATT_MONITOR", 0) != 0

    def get_frame_info(self) -> tuple[int, int]:
        """
        Get frame class and frame type from flight controller parameters.

        Returns:
            tuple[int, int]: (frame_class, frame_type)

        """
        frame_class = int(self.fc_parameters.get("FRAME_CLASS", 1))  # Default to QUAD
        frame_type = int(self.fc_parameters.get("FRAME_TYPE", 1))  # Default to X
        return (frame_class, frame_type)

    @staticmethod
    def __list_network_ports() -> list[str]:
        """List all available network ports."""
        return ["tcp:127.0.0.1:5760", "udp:127.0.0.1:14550"]

    # pylint: disable=duplicate-code
    def __auto_detect_serial(self) -> list[mavutil.SerialPort]:
        preferred_ports = [
            "*FTDI*",
            "*Arduino_Mega_2560*",
            "*3D*",
            "*USB_to_UART*",
            "*Ardu*",
            "*PX4*",
            "*Hex_*",
            "*Holybro_*",
            "*mRo*",
            "*FMU*",
            "*Swift-Flyer*",
            "*Serial*",
            "*CubePilot*",
            "*Qiotek*",
        ]
        serial_list: list[mavutil.SerialPort] = [
            mavutil.SerialPort(device=connection[0], description=connection[1])
            for connection in self.__connection_tuples
            if connection[1] and "mavlink" in connection[1].lower()
        ]
        if len(serial_list) == 1:
            # selected automatically if unique
            return serial_list

        serial_list = mavutil.auto_detect_serial(preferred_list=preferred_ports)
        serial_list.sort(key=lambda x: x.device)

        # remove OTG2 ports for dual CDC
        if (
            len(serial_list) == 2
            and serial_list[0].device.startswith("/dev/serial/by-id")
            and serial_list[0].device[:-1] == serial_list[1].device[0:-1]
        ):
            serial_list.pop(1)

        return serial_list

    # pylint: enable=duplicate-code

    def get_connection_tuples(self) -> list[tuple[str, str]]:
        """Get all available connections."""
        return self.__connection_tuples

    def upload_file(
        self, local_filename: str, remote_filename: str, progress_callback: Union[None, Callable[[int, int], None]] = None
    ) -> bool:
        """Upload a file to the flight controller."""
        if self.master is None:
            return False
        mavftp = MAVFTP(self.master, target_system=self.master.target_system, target_component=self.master.target_component)

        def put_progress_callback(completion: float) -> None:
            if progress_callback is not None and completion is not None:
                progress_callback(int(completion * 100), 100)

        mavftp.cmd_put([local_filename, remote_filename], progress_callback=put_progress_callback)
        ret = mavftp.process_ftp_reply("CreateFile", timeout=10)
        if ret.error_code != 0:
            ret.display_message()
        return ret.error_code == 0

    @staticmethod
    def add_argparse_arguments(parser: ArgumentParser) -> ArgumentParser:
        parser.add_argument(
            "--baudrate",
            type=int,
            default=DEFAULT_BAUDRATE,
            help=_("MAVLink serial connection baudrate to the flight controller. Default is %(default)s"),
        )
        parser.add_argument(  # type: ignore[attr-defined]
            "--device",
            type=str,
            default="",
            help=_(
                "MAVLink connection string to the flight controller. "
                'If set to "none" no connection is made.'
                " Default is autodetection"
            ),
        ).completer = lambda **_: FlightController.__list_serial_ports()  # pyright: ignore[reportAttributeAccessIssue]
        parser.add_argument(
            "-r",
            "--reboot-time",
            type=int,
            min=5,
            max=50,
            action=CheckRange,
            default=DEFAULT_REBOOT_TIME,
            help=_("Flight controller reboot time. Default is %(default)s"),
        )
        return parser
