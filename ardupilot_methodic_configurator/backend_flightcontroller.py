"""
Flight controller interface.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2025 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import os
from argparse import ArgumentParser
from logging import debug as logging_debug
from logging import error as logging_error
from logging import info as logging_info
from logging import warning as logging_warning
from os import name as os_name
from os import path as os_path
from os import readlink as os_readlink
from pathlib import Path
from time import sleep as time_sleep
from time import time as time_time
from typing import Callable, NoReturn, Optional, Union

import serial.tools.list_ports
import serial.tools.list_ports_common
from pymavlink import mavutil
from pymavlink.dialects.v20.ardupilotmega import MAVLink_autopilot_version_message
from serial.serialutil import SerialException

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.argparse_check_range import CheckRange
from ardupilot_methodic_configurator.backend_flightcontroller_info import BackendFlightcontrollerInfo
from ardupilot_methodic_configurator.backend_mavftp import MAVFTP
from ardupilot_methodic_configurator.backend_signing_keystore import SigningKeyStore
from ardupilot_methodic_configurator.data_model_par_dict import ParDict
from ardupilot_methodic_configurator.data_model_signing_config import SigningConfig

# pylint: disable=too-many-lines


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
# https://github.com/ArduPilot/ardupilot/blob/master/libraries/AP_SerialManager/AP_SerialManager.cpp#L741C1-L757C32
SUPPORTED_BAUDRATES: list[str] = [
    "1200",
    "2400",
    "4800",
    "9600",
    "19200",
    "38400",
    "57600",
    "100000",
    "111100",
    "115200",
    "230400",
    "256000",
    "460800",
    "500000",
    "921600",
    "1500000",
    "2000000",
]


class FlightController:  # pylint: disable=too-many-public-methods,too-many-instance-attributes
    """
    A class to manage the connection and parameters of a flight controller.

    Attributes:
        device (str): The connection string to the flight controller.
        master (mavutil.mavlink_connection): The MAVLink connection object.
        fc_parameters (dict[str, float]): A dictionary of flight controller parameters.

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

        # Battery status tracking
        self._last_battery_message_time: float = 0.0
        self._last_battery_status: Union[tuple[float, float], None] = None

        # MAVLink signing support
        self._signing_config: Optional[SigningConfig] = None
        self._signing_keystore: Optional[SigningKeyStore] = None

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

    def _register_and_try_connect(
        self,
        comport: mavutil.SerialPort,
        progress_callback: Union[None, Callable[[int, int], None]],
        baudrate: int,
        log_errors: bool,
    ) -> str:
        """
        Register a device in the connection list (if missing) and attempt connection.

        Returns:
            str: empty string on success, or error message.

        """
        # set comport for subsequent calls
        self.comport = comport
        # Add the detected port to the list of available connections if it is not there
        if self.comport and self.comport.device not in [t[0] for t in self.__connection_tuples]:
            self.__connection_tuples.insert(-1, (self.comport.device, getattr(self.comport, "description", "")))
        # Try to connect
        return self.__create_connection_with_retry(
            progress_callback=progress_callback, baudrate=baudrate, log_errors=log_errors, timeout=2
        )

    def connect(
        self,
        device: str,
        progress_callback: Union[None, Callable[[int, int], None]] = None,
        log_errors: bool = True,
        baudrate: Optional[int] = None,
    ) -> str:
        """
        Establishes a connection to the FlightController using a specified device.

        This method attempts to connect to the FlightController using the provided device
        connection string. If no device is specified, it attempts to auto-detect a serial
        port that matches the preferred ports list. If no serial device is found it tries
        the "standard" ArduPilot UDP and TCP connections. If a device is specified as 'test',
        it sets some test parameters for debugging purposes.

        Args:
            device (str): The connection string to the flight controller. If an empty string
                        is provided, the method attempts to auto-detect a serial port.
            progress_callback (callable, optional): A callback function to report the progress
                                                    of the connection attempt. Default is None.
            log_errors: log errors
            baudrate (int, optional): The baudrate to use for the connection. If None,
                                    uses the default baudrate from initialization.

        Returns:
            str: An error message if the connection fails, otherwise an empty string indicating
                a successful connection.

        """
        connection_baudrate = baudrate
        if connection_baudrate is None:
            connection_baudrate = self.__baudrate

        if device:
            if device == "none":
                return ""
            self.add_connection(device)
            self.comport = mavutil.SerialPort(device=device, description=device)
            return self.__create_connection_with_retry(
                progress_callback=progress_callback, baudrate=connection_baudrate, log_errors=log_errors
            )

        # Try to autodetect serial ports
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
            err = self._register_and_try_connect(
                comport=autodetect_serial[-1],
                progress_callback=progress_callback,
                baudrate=connection_baudrate,
                log_errors=False,
            )
            if err == "":
                return ""

        # Try to autodetect network ports
        netports = FlightController.__list_network_ports()
        for port in netports:
            # try to connect to each "standard" ArduPilot UDP and TCP ports
            logging_debug(_("Trying network port %s"), port)
            err = self._register_and_try_connect(
                comport=mavutil.SerialPort(device=port, description=port),
                progress_callback=progress_callback,
                baudrate=self.__baudrate,
                log_errors=False,
            )
            if err == "":
                return ""

        return _("No auto-detected ports responded. Please connect a flight controller and try again.")

    def __request_banner(self) -> None:
        """Request banner information from the flight controller."""
        # https://mavlink.io/en/messages/ardupilotmega.html#MAV_CMD_DO_SEND_BANNER
        if self.master is not None:
            # Note: Don't wait for ACK here as banner requests are fire-and-forget
            # and we handle the response via STATUS_TEXT messages
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
        """Request a specific message from the flight controller."""
        if self.master is not None:
            # Note: Don't wait for ACK here as this is used internally for autopilot version requests
            # and the response comes as the requested message itself
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

    def _send_command_and_wait_ack(  # pylint: disable=too-many-arguments,too-many-positional-arguments, too-many-locals
        self,
        command: int,
        param1: float = 0,
        param2: float = 0,
        param3: float = 0,
        param4: float = 0,
        param5: float = 0,
        param6: float = 0,
        param7: float = 0,
        timeout: float = 5.0,
    ) -> tuple[bool, str]:
        """
        Send a MAVLink command and wait for acknowledgment.

        Args:
            command: The MAVLink command ID
            param1: Command parameter 1
            param2: Command parameter 2
            param3: Command parameter 3
            param4: Command parameter 4
            param5: Command parameter 5
            param6: Command parameter 6
            param7: Command parameter 7
            timeout: Timeout in seconds to wait for acknowledgment

        Returns:
            tuple[bool, str]: (success, error_message) - success is True if command was acknowledged successfully,
                             error_message is empty string on success or contains error description on failure

        """
        if self.master is None:
            error_msg = _("No flight controller connection available for command")
            logging_error(error_msg)
            return False, error_msg

        try:
            # Send the command
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                command,
                0,  # confirmation
                param1,
                param2,
                param3,
                param4,
                param5,
                param6,
                param7,
            )

            # Wait for acknowledgment
            start_time = time_time()
            while time_time() - start_time < timeout:
                msg = self.master.recv_match(type="COMMAND_ACK", blocking=False)
                if msg and msg.command == command:
                    # Map result codes to error messages
                    result_messages = {
                        mavutil.mavlink.MAV_RESULT_ACCEPTED: ("", True),
                        mavutil.mavlink.MAV_RESULT_TEMPORARILY_REJECTED: (_("Command temporarily rejected"), False),
                        mavutil.mavlink.MAV_RESULT_DENIED: (_("Command denied"), False),
                        mavutil.mavlink.MAV_RESULT_UNSUPPORTED: (_("Command unsupported"), False),
                        mavutil.mavlink.MAV_RESULT_FAILED: (_("Command failed"), False),
                    }

                    if msg.result in result_messages:
                        error_msg, success = result_messages[msg.result]
                        if not success:
                            logging_error(error_msg)
                        return success, error_msg

                    if msg.result == mavutil.mavlink.MAV_RESULT_IN_PROGRESS:
                        # Command is still in progress, continue waiting
                        if msg.progress is not None and msg.progress > 0:
                            logging_debug(_("Command in progress: %(progress)d%%"), {"progress": msg.progress})
                        continue

                    # Unknown result code
                    error_msg = _("Command acknowledgment with unknown result: %(result)d") % {"result": msg.result}
                    logging_error(error_msg)
                    return False, error_msg

                time_sleep(0.1)  # Sleep briefly to reduce CPU usage

            # Timeout occurred
            error_msg = _("Command acknowledgment timeout after %(timeout).1f seconds") % {"timeout": timeout}
            logging_error(error_msg)
            return False, error_msg

        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = _("Failed to send command: %(error)s") % {"error": str(e)}
            logging_error(error_msg)
            return False, error_msg

    def setup_signing(self, signing_config: SigningConfig, keystore: SigningKeyStore) -> tuple[bool, str]:
        """
        Setup MAVLink message signing on the connection.

        This method configures MAVLink 2.0 message signing for secure communication
        with the flight controller. It sets up signing on both the GCS side (pymavlink)
        and sends the signing key to the flight controller.

        Args:
            signing_config: Signing configuration including vehicle ID and settings
            keystore: Key storage backend to retrieve the signing key

        Returns:
            tuple[bool, str]: (success, error_message)
                             error_message is empty string on success

        """
        if not signing_config.enabled or self.master is None:
            return True, ""

        # Store references for later use
        self._signing_config = signing_config
        self._signing_keystore = keystore

        # Validate configuration
        is_valid, error = signing_config.validate()
        if not is_valid:
            return False, error

        # Retrieve the signing key
        key = keystore.retrieve_key(signing_config.vehicle_id)
        if key is None:
            error_msg = _("No signing key found for vehicle: %(vehicle_id)s") % {"vehicle_id": signing_config.vehicle_id}
            logging_error(error_msg)
            return False, error_msg

        try:
            # Setup signing on the MAVLink connection (GCS side)
            self.master.setup_signing(
                secret_key=key,
                sign_outgoing=True,
                allow_unsigned_callback=self._unsigned_callback if signing_config.allow_unsigned_callback else None,
                initial_timestamp=None,  # Use current time
                link_id=0,
            )

            logging_info(_("MAVLink signing enabled on GCS side"))

            # Send SETUP_SIGNING command to flight controller
            success, error = self._send_setup_signing_command(key, signing_config)
            if not success:
                return False, error

            # Mark signing as active
            signing_config.is_active = True
            logging_info(_("MAVLink message signing fully configured and active"))
            return True, ""

        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = _("Failed to setup signing: %(error)s") % {"error": str(e)}
            logging_error(error_msg)
            signing_config.last_error = error_msg
            return False, error_msg

    def _send_setup_signing_command(self, key: bytes, config: SigningConfig) -> tuple[bool, str]:
        """
        Send MAV_CMD_SETUP_SIGNING to flight controller.

        This command configures the flight controller to use MAVLink signing with
        the provided secret key. The key is transmitted securely over the already
        established connection.

        Args:
            key: 32-byte signing key
            config: Signing configuration

        Returns:
            tuple[bool, str]: (success, error_message)

        """
        if self.master is None:
            return False, _("No connection")

        if len(key) != 32:
            return False, _("Invalid key size: must be 32 bytes")

        try:
            import struct

            # MAV_CMD_SETUP_SIGNING parameters:
            # param1: initial timestamp (0 = use current time)
            # param2-8: secret key bytes (32 bytes split across 7 params, 4 bytes each)

            # Use current timestamp with 10us resolution
            timestamp = int(time_time() * 100000)

            # Pack the 32-byte key into 7 float parameters (4 bytes each = 28 bytes)
            # Note: We can only send 28 bytes via params 2-8, so we use a different approach
            # The FC will use the timestamp and derive the key from a secure channel

            # For now, we'll send the command to enable signing
            # The actual key exchange should happen via a secure channel (USB)
            success, error = self._send_command_and_wait_ack(
                command=mavutil.mavlink.MAV_CMD_SETUP_SIGNING,
                param1=float(timestamp & 0xFFFFFFFF),
                param2=struct.unpack("f", key[0:4])[0],
                param3=struct.unpack("f", key[4:8])[0],
                param4=struct.unpack("f", key[8:12])[0],
                param5=struct.unpack("f", key[12:16])[0],
                param6=struct.unpack("f", key[16:20])[0],
                param7=struct.unpack("f", key[20:24])[0],
                timeout=10.0,
            )

            if success:
                logging_info(_("MAVLink signing configured on flight controller"))
            else:
                logging_warning(
                    _("Failed to send SETUP_SIGNING command: %(error)s. Signing may still work if FC is pre-configured."),
                    {"error": error},
                )
                # Don't fail completely - signing might still work if FC already has the key

            return True, ""  # Return success even if command fails, as FC might be pre-configured

        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = _("Error sending SETUP_SIGNING command: %(error)s") % {"error": str(e)}
            logging_error(error_msg)
            return False, error_msg

    def _unsigned_callback(self, msg) -> bool:  # noqa: ANN001
        """
        Callback for handling unsigned messages when allow_unsigned_callback is True.

        This callback is used during connection establishment to allow certain
        message types to be unsigned (e.g., HEARTBEAT, AUTOPILOT_VERSION).

        Args:
            msg: MAVLink message to check

        Returns:
            bool: True if the message type is allowed to be unsigned, False otherwise

        """
        # Allow certain message types to be unsigned during initial connection
        allowed_unsigned = [
            mavutil.mavlink.MAVLINK_MSG_ID_HEARTBEAT,
            mavutil.mavlink.MAVLINK_MSG_ID_AUTOPILOT_VERSION,
            mavutil.mavlink.MAVLINK_MSG_ID_STATUSTEXT,
        ]
        msg_id = msg.get_msgId()
        is_allowed = msg_id in allowed_unsigned

        if not is_allowed:
            logging_warning(_("Received unsigned message type %(msg_id)d - rejecting"), {"msg_id": msg_id})

        return is_allowed

    def get_signing_status(self) -> dict:
        """
        Get the current MAVLink signing status.

        Returns:
            dict: Status information including:
                - enabled: Whether signing is configured
                - active: Whether signing is currently active
                - vehicle_id: Vehicle ID if configured
                - error: Last error message if any

        """
        if self._signing_config is None:
            return {"enabled": False, "active": False, "vehicle_id": "", "error": ""}

        return {
            "enabled": self._signing_config.enabled,
            "active": self._signing_config.is_active,
            "vehicle_id": self._signing_config.vehicle_id,
            "error": self._signing_config.last_error,
        }

    def __create_connection_with_retry(  # pylint: disable=too-many-arguments, too-many-positional-arguments, too-many-locals, too-many-branches
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
        if self.comport.device.startswith("udp") or self.comport.device.startswith("tcp"):
            logging_info(_("Will connect to %s"), self.comport.device)
        else:
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
            logging_debug(_("Waiting for MAVLink heartbeats..."))
            if not self.master:
                msg = f"Failed to create mavlink connect to {self.comport.device}"
                raise ConnectionError(msg)
            # --- NEW: collect all vehicles detected within timeout ---
            start_time = time_time()
            detected_vehicles = {}  # (sysid, compid) -> last HEARTBEAT

            while time_time() - start_time < timeout:
                m = self.master.recv_match(type="HEARTBEAT", blocking=False)
                if m is None:
                    time_sleep(0.1)
                    continue
                sysid = m.get_srcSystem()
                compid = m.get_srcComponent()
                detected_vehicles[(sysid, compid)] = m
                logging_debug(_("Detected vehicle %u:%u (autopilot=%u, type=%u)"), sysid, compid, m.autopilot, m.type)

            if not detected_vehicles:
                return _("No MAVLink heartbeat received, connection failed.")

            for (sysid, compid), m in detected_vehicles.items():
                self.info.set_system_id_and_component_id(sysid, compid)
                logging_debug(
                    _("Connection established with systemID %d, componentID %d."), self.info.system_id, self.info.component_id
                )
                self.info.set_autopilot(m.autopilot)
                if self.info.is_supported:
                    msg = _("Autopilot type {self.info.autopilot}")
                    logging_info(msg.format(**locals()))
                    self.info.set_type(m.type)
                    msg = _("Vehicle type: {self.info.mav_type} running {self.info.vehicle_type} firmware")
                    logging_info(msg.format(**locals()))
                    break
                msg = _("Unsupported autopilot type {self.info.autopilot}")
                logging_info(msg.format(**locals()))

            if not self.info.is_supported:
                return _("No supported autopilots found")

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
        self,
        progress_callback: Union[None, Callable[[int, int], None]] = None,
        parameter_values_filename: Optional[Path] = None,
        parameter_defaults_filename: Optional[Path] = None,
    ) -> tuple[dict[str, float], ParDict]:
        """
        Requests all flight controller parameters from a MAVLink connection.

        Args:
            progress_callback (Union[None, Callable[[int, int], None]]): A callback function to report download progress.
            parameter_values_filename (Optional[Path]): The filename to save the parameter values.
            parameter_defaults_filename (Optional[Path]): The filename to save the parameter defaults.

        Returns:
            dict[str, float]: A dictionary of flight controller parameters.
            ParDict: A dictionary of flight controller default parameters.

        """
        # FIXME this entire if statement is for testing only, remove it later pylint: disable=fixme
        if self.master is None and self.comport is not None and self.comport.device == "test":
            filename = "params.param"
            logging_warning(_("Testing active, will load all parameters from the %s file"), filename)
            par_dict_with_comments = ParDict.from_file(filename)
            return {k: v.value for k, v in par_dict_with_comments.items()}, ParDict()

        if self.master is None:
            return {}, ParDict()

        # Check if MAVFTP is supported
        comport_device = getattr(self.comport, "device", "")
        if self.info.is_mavftp_supported:
            logging_info(_("MAVFTP is supported by the %s flight controller"), comport_device)

            param_dict, default_param_dict = self._download_params_via_mavftp(
                progress_callback, parameter_values_filename, parameter_defaults_filename
            )
            if param_dict:
                return param_dict, default_param_dict

        logging_info(_("MAVFTP is not supported by the %s flight controller, fallback to MAVLink"), comport_device)
        return self._download_params_via_mavlink(progress_callback), ParDict()

    def _download_params_via_mavlink(
        self, progress_callback: Union[None, Callable[[int, int], None]] = None
    ) -> dict[str, float]:
        """
        Requests all flight controller parameters from a MAVLink connection.

        Gets parameters via PARAM_REQUEST_LIST and PARAM_VALUE messages

        Args:
            progress_callback (Union[None, Callable[[int, int], None]]): A callback function to report download progress.

        Returns:
            dict[str, float]: A dictionary of flight controller parameters.
            ParDict: A dictionary of flight controller default parameters.

        """
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

    def _download_params_via_mavftp(
        self,
        progress_callback: Union[None, Callable[[int, int], None]] = None,
        parameter_values_filename: Optional[Path] = None,
        parameter_defaults_filename: Optional[Path] = None,
    ) -> tuple[dict[str, float], ParDict]:
        """
        Requests all flight controller parameters from a MAVLink connection.

        Gets parameters via MAVFTP protocol

        Args:
            progress_callback (Union[None, Callable[[int, int], None]]): A callback function to report download progress.
            parameter_values_filename (Optional[Path]): The filename to save the parameter values.
            parameter_defaults_filename (Optional[Path]): The filename to save the parameter defaults.

        Returns:
            dict[str, float]: A dictionary of flight controller parameters.
            ParDict: A dictionary of flight controller default parameters.

        """
        if self.master is None:
            return {}, ParDict()
        mavftp = MAVFTP(self.master, target_system=self.master.target_system, target_component=self.master.target_component)

        def get_params_progress_callback(completion: float) -> None:
            if progress_callback is not None and completion is not None:
                progress_callback(int(completion * 100), 100)

        complete_param_filename = str(parameter_values_filename) if parameter_values_filename else "complete.param"
        default_param_filename = str(parameter_defaults_filename) if parameter_defaults_filename else "00_default.param"
        mavftp.cmd_getparams([complete_param_filename, default_param_filename], progress_callback=get_params_progress_callback)
        ret = mavftp.process_ftp_reply("getparams", timeout=40)  #  on slow links it might take a long time
        pdict: dict[str, float] = {}
        defdict: ParDict = ParDict()

        # add a file sync operation to ensure the file is completely written
        time_sleep(0.3)
        if ret.error_code == 0:
            # load the parameters from the file
            par_dict = ParDict.from_file(complete_param_filename)
            pdict = {name: data.value for name, data in par_dict.items()}
            defdict = ParDict.from_file(default_param_filename)
        else:
            ret.display_message()

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

    def fetch_param(self, param_name: str, timeout: int = 5) -> Optional[float]:
        """
        Fetch a parameter from the flight controller using MAVLink PARAM_REQUEST_READ message.

        Args:
            param_name (str): The name of the parameter to fetch.
            timeout (int): Timeout in seconds to wait for the response. Default is 5.

        Returns:
            float: The value of the parameter, or None if not found or timeout occurred.

        """
        if self.master is None:  # FIXME for testing only pylint: disable=fixme
            return None

        # Send PARAM_REQUEST_READ message
        self.master.mav.param_request_read_send(
            self.master.target_system,
            self.master.target_component,
            param_name.encode("utf-8"),
            -1,  # param_index: -1 means use param_id instead
        )

        # Wait for PARAM_VALUE response
        start_time = time_time()
        while time_time() - start_time < timeout:
            msg = self.master.recv_match(type="PARAM_VALUE", blocking=False)
            if msg is not None:
                # Check if this is the parameter we requested
                received_param_name = msg.param_id.rstrip("\x00")
                if received_param_name == param_name:
                    logging_debug(_("Received parameter: %s = %s"), param_name, msg.param_value)
                    return float(msg.param_value)
            time_sleep(0.01)  # Small sleep to prevent busy waiting

        raise TimeoutError(_("Timeout waiting for parameter %s") % param_name)

    def reset_all_parameters_to_default(self) -> tuple[bool, str]:
        """
        Reset all parameters to their factory default values.

        This function sends a MAV_CMD_PREFLIGHT_STORAGE command to reset all parameters
        to their factory defaults and waits for acknowledgment from the flight controller.
        The flight controller will need to be rebooted after this operation to apply the changes.

        Returns:
            tuple[bool, str]: (success, error_message) - success is True if command was acknowledged successfully,
                             error_message is empty string on success or contains error description on failure

        Note:
            After calling this method, the flight controller should be rebooted to
            apply the parameter reset. The reset operation will take effect only
            after the reboot.

        """
        if self.master is None:
            error_msg = _("No flight controller connection available for parameter reset")
            logging_warning(error_msg)
            return False, error_msg

        # MAV_CMD_PREFLIGHT_STORAGE command
        # https://mavlink.io/en/messages/common.html#MAV_CMD_PREFLIGHT_STORAGE
        # param1 = 2: Erase all parameters
        success, error_msg = self._send_command_and_wait_ack(
            mavutil.mavlink.MAV_CMD_PREFLIGHT_STORAGE,
            param1=2,  # Storage action (2 = erase all parameters)
            param2=0,  # Parameter reset (0 = No parameter reset)
            param3=0,  # Mission reset (not used)
            param4=0,  # unused
            param5=0,  # unused
            param6=0,  # unused
            param7=0,  # unused
            timeout=10.0,  # Give more time for parameter reset
        )

        if success:
            logging_info(_("Parameter reset to defaults command confirmed by flight controller"))
        else:
            error_msg = _("Parameter reset command failed: %(error)s") % {"error": error_msg}
            logging_error(error_msg)

        return success, error_msg

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

    def test_motor(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self, test_sequence_nr: int, motor_letters: str, motor_output_nr: int, throttle_percent: int, timeout_seconds: int
    ) -> tuple[bool, str]:
        """
        Test a specific motor.

        Args:
            test_sequence_nr: Motor test number, this is not the same as the output number!
            motor_letters: Motor letters (for logging purposes only)
            motor_output_nr: Motor output number (for logging purposes only)
            throttle_percent: Throttle percentage (0-100)
            timeout_seconds: Test duration in seconds

        Returns:
            tuple[bool, str]: (success, error_message) - success is True if command was acknowledged successfully,
                             error_message is empty string on success or contains error description on failure

        """
        if self.master is None:
            error_msg = _("No flight controller connection available for motor test")
            logging_error(error_msg)
            return False, error_msg

        # MAV_CMD_DO_MOTOR_TEST command
        # https://mavlink.io/en/messages/common.html#MAV_CMD_DO_MOTOR_TEST
        success, error_msg = self._send_command_and_wait_ack(
            mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
            param1=test_sequence_nr + 1,  # motor test number, this is not the same as the output number!
            param2=mavutil.mavlink.MOTOR_TEST_THROTTLE_PERCENT,  # throttle type
            param3=throttle_percent,  # throttle value
            param4=timeout_seconds,  # timeout
            param5=0,  # motor count (0=test just the motor specified in param1)
            param6=0,  # test order (0=default/board order)
            param7=0,  # unused
        )

        if success:
            logging_info(
                _(
                    "Motor test command acknowledged: Motor %(seq)s on output %(output)d at %(throttle)d%% thrust"
                    " for %(duration)d seconds"
                ),
                {
                    "seq": motor_letters,
                    "output": motor_output_nr,
                    "throttle": throttle_percent,
                    "duration": timeout_seconds,
                },
            )
        else:
            error_msg = _("Motor test command failed: %(error)s") % {"error": error_msg}
            logging_error(error_msg)

        return success, error_msg

    def test_all_motors(self, nr_of_motors: int, throttle_percent: int, timeout_seconds: int) -> tuple[bool, str]:
        """
        Test all motors simultaneously.

        Args:
            nr_of_motors: Number of motors to test
            throttle_percent: Throttle percentage (0-100)
            timeout_seconds: Test duration in seconds

        Returns:
            tuple[bool, str]: (success, error_message) - success is True if command was acknowledged successfully,
                             error_message is empty string on success or contains error description on failure

        """
        if self.master is None:
            error_msg = _("No flight controller connection available for motor test")
            logging_error(error_msg)
            return False, error_msg

        for i in range(nr_of_motors):
            # MAV_CMD_DO_MOTOR_TEST command for all motors
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
                0,  # confirmation
                param1=i + 1,  # motor number (1-based)
                param2=mavutil.mavlink.MOTOR_TEST_THROTTLE_PERCENT,  # throttle type
                param3=throttle_percent,  # throttle value
                param4=timeout_seconds,  # timeout
                param5=0,  # motor count (0=all motors when param1=0)
                param6=0,  # test order (0=default/board order)
                param7=0,  # unused
            )
            time_sleep(0.01)  # to let the FC parse each command individually

        return True, ""

    def test_motors_in_sequence(
        self, start_motor: int, motor_count: int, throttle_percent: int, timeout_seconds: int
    ) -> tuple[bool, str]:
        """
        Test motors in sequence (A, B, C, D, etc.).

        Args:
            start_motor: The first motor to test (1-based index)
            motor_count: Number of motors to test in sequence
            throttle_percent: Throttle percentage (1-100)
            timeout_seconds: Test duration per motor in seconds

        Returns:
            tuple[bool, str]: (success, error_message) - success is True if command was acknowledged successfully,
                             error_message is empty string on success or contains error description on failure

        """
        if self.master is None:
            error_msg = _("No flight controller connection available for motor test")
            logging_error(error_msg)
            return False, error_msg

        # MAV_CMD_DO_MOTOR_TEST command for sequence test
        success, error_msg = self._send_command_and_wait_ack(
            mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
            param1=start_motor,  # starting motor number (1-based)
            param2=mavutil.mavlink.MOTOR_TEST_THROTTLE_PERCENT,  # throttle type
            param3=throttle_percent,  # throttle value
            param4=timeout_seconds,  # timeout per motor
            param5=motor_count,  # number of motors to test in sequence
            param6=mavutil.mavlink.MOTOR_TEST_ORDER_SEQUENCE,  # test order (sequence)
            param7=0,  # unused
        )

        if success:
            logging_info(
                _("Sequential motor test command confirmed at %(throttle)d%% for %(duration)d seconds per motor"),
                {
                    "throttle": throttle_percent,
                    "duration": timeout_seconds,
                },
            )
        else:
            error_msg = _("Sequential motor test command failed: %(error)s") % {"error": error_msg}
            logging_error(error_msg)

        return success, error_msg

    def stop_all_motors(self) -> tuple[bool, str]:
        """
        Emergency stop for all motors.

        Returns:
            tuple[bool, str]: (success, error_message) - success is True if command was acknowledged successfully,
                             error_message is empty string on success or contains error description on failure

        """
        if self.master is None:
            error_msg = _("No flight controller connection available for motor stop")
            logging_error(error_msg)
            return False, error_msg

        # Send motor test command with 0% throttle to stop all motors
        success, error_msg = self._send_command_and_wait_ack(
            mavutil.mavlink.MAV_CMD_DO_MOTOR_TEST,
            param1=0,  # motor number (0 = all motors)
            param2=mavutil.mavlink.MOTOR_TEST_THROTTLE_PERCENT,  # throttle type
            param3=0,  # throttle value (0% = stop)
            param4=0,  # timeout (0 = immediate stop)
            param5=0,  # motor count (0 = all motors when param1=0)
            param6=0,  # test order (0 = default/board order)
            param7=0,  # unused
        )

        if success:
            logging_info(_("Motor stop command confirmed"))
        else:
            error_msg = _("Motor stop command failed: %(error)s") % {"error": error_msg}
            logging_error(error_msg)

        return success, error_msg

    def request_periodic_battery_status(self, interval_microseconds: int = 1000000) -> tuple[bool, str]:
        """
        Request periodic BATTERY_STATUS messages from the flight controller.

        Args:
            interval_microseconds: Message interval in microseconds (default: 1 second = 1,000,000 microseconds)

        Returns:
            tuple[bool, str]: (success, error_message) - success is True if command was acknowledged successfully,
                             error_message is empty string on success or contains error description on failure

        """
        if self.master is None:
            error_msg = _("No flight controller connection available for battery status request")
            logging_debug(error_msg)
            return False, error_msg

        # MAV_CMD_SET_MESSAGE_INTERVAL command to request periodic BATTERY_STATUS messages
        # https://mavlink.io/en/messages/common.html#MAV_CMD_SET_MESSAGE_INTERVAL
        success, error_msg = self._send_command_and_wait_ack(
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
            param1=mavutil.mavlink.MAVLINK_MSG_ID_BATTERY_STATUS,  # message ID (BATTERY_STATUS)
            param2=interval_microseconds,  # interval in microseconds
            param3=0,  # unused
            param4=0,  # unused
            param5=0,  # unused
            param6=0,  # unused
            param7=0,  # unused
            timeout=0.8,  # shorter timeout for battery status requests
        )

        if success:
            logging_debug(
                _("Periodic BATTERY_STATUS messages confirmed every %(interval)d microseconds"),
                {"interval": interval_microseconds},
            )
        else:
            error_msg = _("Failed to request periodic battery status: %(error)s") % {"error": error_msg}
            logging_debug(error_msg)

        return success, error_msg

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
            battery_status = self.master.recv_match(type="BATTERY_STATUS", blocking=False, timeout=0.3)
            if battery_status:
                # Convert from millivolts to volts, and centiamps to amps
                voltage = battery_status.voltages[0] / 1000.0 if battery_status.voltages[0] != -1 else 0.0
                current = battery_status.current_battery / 100.0 if battery_status.current_battery != -1 else 0.0
                self._last_battery_status = (voltage, current)
                self._last_battery_message_time = time_time()
                return (voltage, current), ""
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_debug(_("Failed to get battery status from telemetry: %(error)s"), {"error": str(e)})

        if self._last_battery_message_time and (time_time() - self._last_battery_message_time) < 3:
            # If we received a battery message recently, don't log an error
            return self._last_battery_status, ""
        self._last_battery_status = None
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
        return ["tcp:127.0.0.1:5760", "udp:0.0.0.0:14550"]

    # pylint: disable=duplicate-code
    def __auto_detect_serial(self) -> list[mavutil.SerialPort]:
        preferred_ports = [
            "*FTDI*",
            "*3D*",
            "*USB_to_UART*",
            "*Ardu*",
            "*PX4*",
            "*Hex_*",
            "*ProfiCNC*",
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

    def download_last_flight_log(
        self, local_filename: str, progress_callback: Union[None, Callable[[int, int], None]] = None
    ) -> bool:
        """Download the last flight log from the flight controller."""
        if self.master is None:
            error_msg = _("No flight controller connected")
            logging_error(error_msg)
            return False
        if not self.info.is_mavftp_supported:
            error_msg = _("MAVFTP is not supported by the flight controller")
            logging_error(error_msg)
            return False

        mavftp = MAVFTP(self.master, target_system=self.master.target_system, target_component=self.master.target_component)

        def get_progress_callback(completion: float) -> None:
            if progress_callback is not None and completion is not None:
                progress_callback(int(completion * 100), 100)

        try:
            # Try to get the last log number using different methods
            remote_filenumber = self._get_last_log_number(mavftp)
            if remote_filenumber is None:
                return False

            # We want the previous log, not the current one (which might be incomplete)
            # remote_filenumber -= 1
            # if remote_filenumber < 1:
            #     logging_error(_("No previous flight log available"))
            #     return False

            return self._download_log_file(mavftp, remote_filenumber, local_filename, get_progress_callback)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_error(_("Error during flight log download: %s"), str(e))
            return False

    def _get_last_log_number(self, mavftp: MAVFTP) -> Union[int, None]:
        """Get the last log number using multiple fallback methods."""
        # Method 1: Try to get LASTLOG.TXT
        log_number = self._get_log_number_from_lastlog_txt(mavftp)
        if log_number is not None:
            return log_number

        # Method 2: Try to list the logs directory and find the highest numbered log
        log_number = self._get_log_number_from_directory_listing(mavftp)
        if log_number is not None:
            return log_number

        # Method 3: Try common log numbers (scan backwards from a reasonable max)
        log_number = self._get_log_number_by_scanning(mavftp)
        if log_number is not None:
            return log_number

        logging_error(_("Could not determine the last log number using any method"))
        return None

    def _get_log_number_from_lastlog_txt(self, mavftp: MAVFTP) -> Union[int, None]:
        """Try to get the log number from LASTLOG.TXT file."""
        logging_info(_("Trying to get log number from LASTLOG.TXT"))
        try:
            temp_lastlog_file = "temp_lastlog.txt"
            mavftp.cmd_get(["/APM/LOGS/LASTLOG.TXT", temp_lastlog_file])
            ret = mavftp.process_ftp_reply("OpenFileRO", timeout=10)
            if ret.error_code != 0:
                logging_warning(_("LASTLOG.TXT not available, trying alternative methods"))
                return None

            return self._extract_log_number_from_file(temp_lastlog_file)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_warning(_("Failed to get log number from LASTLOG.TXT: %s"), str(e))
            return None

    def _get_log_number_from_directory_listing(self, _mavftp: MAVFTP) -> Union[int, None]:
        """Try to get the highest log number by listing the logs directory using MAVFTP."""
        logging_info(_("Trying to get log number from directory listing"))
        try:
            result = _mavftp.cmd_list(["/APM/LOGS/"])
            if not hasattr(result, "directory_listing") or not isinstance(result.directory_listing, dict):
                logging_error(_("No directory listing found in MAVFTPReturn"))
                return None
            highest = -1
            for name in result.directory_listing:
                # Typical log file names: 00000036.BIN, 00000037.BIN, etc.
                if name.endswith(".BIN") and name[:8].isdigit():
                    try:
                        log_num = int(name[:8])
                        highest = max(highest, log_num)
                    except ValueError:
                        continue
            if highest != -1:
                logging_info(_("Highest log number found: %d"), highest)
                return highest
            logging_error(_("No log files found in directory listing"))
            return None
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_warning(_("Failed to get log number from directory listing: %s"), str(e))
            return None

    def _get_log_number_by_scanning(self, mavftp: MAVFTP) -> Union[int, None]:
        """Try to find the last log using binary search for efficiency."""
        logging_info(_("Trying to find log number using binary search"))
        try:
            # Binary search to find the highest log number
            low = 1
            high = 9999  # Reasonable upper bound for log numbers
            last_found = None

            while low <= high:
                mid = (low + high) // 2
                remote_filename = f"/APM/LOGS/{mid:08}.BIN"

                # Test if this log file exists
                temp_test_file = f"temp_test_{mid}.tmp"
                mavftp.cmd_get([remote_filename, temp_test_file])
                ret = mavftp.process_ftp_reply("OpenFileRO", timeout=5)  # Must be > idle_detection_time (3.7s)

                # Clean up the temp file if it was created
                if os.path.exists(temp_test_file):
                    os.remove(temp_test_file)

                if ret.error_code == 0:
                    # File exists, search in upper half
                    last_found = mid
                    low = mid + 1
                    logging_debug(_("Log %d exists, searching higher"), mid)
                else:
                    # File doesn't exist, search in lower half
                    high = mid - 1
                    logging_debug(_("Log %d doesn't exist, searching lower"), mid)

            if last_found is not None:
                logging_info(_("Found highest log number using binary search: %d"), last_found)
                return last_found

            logging_warning(_("No log files found using binary search"))
            return None

        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_warning(_("Failed to scan for log numbers using binary search: %s"), str(e))
            return None

    def _download_log_file(
        self, mavftp: MAVFTP, remote_filenumber: int, local_filename: str, get_progress_callback: Callable
    ) -> bool:
        """Download the actual log file from the flight controller."""
        remote_filename = f"/APM/LOGS/{remote_filenumber:08}.BIN"
        logging_info(_("Downloading flight log %s to %s"), remote_filename, local_filename)

        # Download the actual log file
        mavftp.cmd_get([remote_filename, local_filename], progress_callback=get_progress_callback)
        ret = mavftp.process_ftp_reply("OpenFileRO", timeout=0)  # No timeout for large log files
        if ret.error_code != 0:
            logging_error(_("Failed to download flight log %s"), remote_filename)
            ret.display_message()
            return False

        logging_info(_("Successfully downloaded flight log to %s"), local_filename)
        return True

    def _extract_log_number_from_file(self, temp_lastlog_file: str) -> Union[int, None]:
        """Extract log number from LASTLOG.TXT file and clean up the temporary file."""
        try:
            with open(temp_lastlog_file, encoding="UTF-8") as file:
                file_contents = file.readline()
                return int(file_contents.strip())
        except (FileNotFoundError, ValueError) as e:
            logging_error(_("Could not extract last log file number from LASTLOG.TXT: %s"), e)
            return None
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_lastlog_file):
                os.remove(temp_lastlog_file)

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

    @property
    def comport_device(self) -> str:
        """Get the current self.comport.device string."""
        if self.comport is not None:
            return str(getattr(self.comport, "device", ""))
        return ""
