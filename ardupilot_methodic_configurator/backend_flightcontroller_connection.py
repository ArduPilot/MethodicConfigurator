"""
Flight controller connection management.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

import contextlib
from logging import debug as logging_debug
from logging import error as logging_error
from logging import info as logging_info
from logging import warning as logging_warning
from os import name as os_name
from os import path as os_path
from os import readlink as os_readlink
from time import sleep as time_sleep
from time import time as time_time
from typing import TYPE_CHECKING, Any, Callable, ClassVar, NoReturn, Optional, Union, no_type_check

import serial.tools.list_ports
import serial.tools.list_ports_common
from pymavlink import mavutil
from pymavlink.dialects.v20.ardupilotmega import MAVLink_autopilot_version_message
from serial.serialutil import SerialException
from serial.tools.list_ports_common import ListPortInfo

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller_factory_mavlink import (
    MavlinkConnectionFactory,
    SystemMavlinkConnectionFactory,
)
from ardupilot_methodic_configurator.backend_flightcontroller_factory_serial import (
    SerialPortDiscovery,
    SystemSerialPortDiscovery,
)
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo

if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller_protocols import MavlinkConnection


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
DEVICE_FC_PARAM_FROM_FILE: str = "file"  # Special device name to simulate FC parameters from params.param file
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


class FlightControllerConnection:  # pylint: disable=too-many-instance-attributes
    """
    Manages flight controller connection establishment and lifecycle.

    This class handles all aspects of connecting to a flight controller:
    - Port discovery (serial and network)
    - Connection establishment with retries
    - Vehicle detection from heartbeats
    - Autopilot version and banner retrieval
    - Connection error handling and guidance
    """

    # Connection timeout constants
    CONNECTION_RETRY_COUNT: ClassVar[int] = 3
    CONNECTION_TIMEOUT: ClassVar[int] = 5
    CONNECTION_RETRY_TIMEOUT: ClassVar[int] = 2
    HEARTBEAT_POLL_DELAY: ClassVar[float] = 0.1
    BANNER_RECEIVE_TIMEOUT: ClassVar[float] = 1.0

    # Default network ports to try
    DEFAULT_NETWORK_PORTS: ClassVar[list[str]] = [
        "tcp:127.0.0.1:5760",
        "udp:0.0.0.0:14550",
    ]

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        info: FlightControllerInfo,
        baudrate: int = DEFAULT_BAUDRATE,
        network_ports: Optional[list[str]] = None,
        serial_port_discovery: Optional[SerialPortDiscovery] = None,
        mavlink_connection_factory: Optional[MavlinkConnectionFactory] = None,
    ) -> None:
        """
        Initialize the connection manager.

        Args:
            info: Flight controller information object to populate
            baudrate: Default baud rate for serial connections
            network_ports: Optional list of network ports to try (overrides defaults)
            serial_port_discovery: Optional serial port discovery service
            mavlink_connection_factory: Optional MAVLink connection factory service

        """
        self.info = info
        self.master: Optional[MavlinkConnection] = None
        self.comport: Union[mavutil.SerialPort, serial.tools.list_ports_common.ListPortInfo, None] = None
        self._baudrate = baudrate
        self._network_ports = list(network_ports) if network_ports is not None else self.DEFAULT_NETWORK_PORTS[:]
        self._connection_tuples: list[tuple[str, str]] = []
        self._serial_port_discovery: SerialPortDiscovery = serial_port_discovery or SystemSerialPortDiscovery()
        self._mavlink_connection_factory: MavlinkConnectionFactory = (
            mavlink_connection_factory or SystemMavlinkConnectionFactory()
        )

    def discover_connections(self) -> None:
        """
        Discover all available connections (serial and network ports).

        Populates the list of available serial ports and network ports
        that can be used to connect to a flight controller.
        """
        comports = self._serial_port_discovery.get_available_ports()
        netports = self.get_network_ports()
        # list of tuples with the first element being the port name and the second element being the port description
        self._connection_tuples = [(port.device, port.description) for port in comports] + [(port, port) for port in netports]
        logging_info(_("Available connection ports are:"))
        for port in self._connection_tuples:
            logging_info("%s - %s", port[0], port[1])
        # now that it is logged, add the 'Add another' tuple
        self._connection_tuples += [(_("Add another"), _("Add another"))]

    def disconnect(self) -> None:
        """Close the connection to the flight controller."""
        if self.master is not None:
            with contextlib.suppress(Exception):
                self.master.close()  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue]
            self.master = None
        self.info.reset()

    def add_connection(self, connection_string: str) -> bool:
        """
        Add a connection string to the list of available connections.

        Args:
            connection_string: Connection string (e.g., "COM3", "tcp:localhost:5760")

        Returns:
            bool: True if connection string is valid and added

        """
        if connection_string:
            # Check if connection_string is not the first element of any tuple in self._connection_tuples
            if all(connection_string != t[0] for t in self._connection_tuples):
                self._connection_tuples.insert(-1, (connection_string, connection_string))
                logging_debug(_("Added connection %s"), connection_string)
                return True
            logging_debug(_("Did not add duplicated connection %s"), connection_string)
        else:
            logging_debug(_("Did not add empty connection"))
        return False

    def _register_and_try_connect(
        self,
        comport: Union[mavutil.SerialPort, serial.tools.list_ports_common.ListPortInfo],
        progress_callback: Union[None, Callable[[int, int], None]],
        baudrate: int,
        log_errors: bool,
    ) -> str:
        """
        Register a device in the connection list (if missing) and attempt connection.

        Args:
            comport: Serial port object to register and connect to
            progress_callback: Optional callback for progress updates
            baudrate: Baud rate for serial connections
            log_errors: Whether to log errors

        Returns:
            str: empty string on success, or error message.

        """
        # set comport for subsequent calls
        self.comport = comport
        # Add the detected port to the list of available connections if it is not there
        if self.comport and self.comport.device not in [t[0] for t in self._connection_tuples]:
            self._connection_tuples.insert(-1, (self.comport.device, getattr(self.comport, "description", "")))
        # Try to connect
        return self.create_connection_with_retry(
            progress_callback=progress_callback,
            baudrate=baudrate,
            log_errors=log_errors,
            timeout=self.CONNECTION_RETRY_TIMEOUT,
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
        the "standard" ArduPilot UDP and TCP connections.

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
        connection_baudrate = baudrate if baudrate is not None else self._baudrate

        # Always clear cached metadata before attempting a new connection so UI
        # components never display stale data while we probe ports.
        self.info.reset()

        if device:
            if device == "none":
                return ""
            self.add_connection(device)
            self.comport = mavutil.SerialPort(device=device, description=device)
            return self.create_connection_with_retry(
                progress_callback=progress_callback, baudrate=connection_baudrate, log_errors=log_errors
            )

        # Try to autodetect serial ports
        autodetect_serial = self._auto_detect_serial()
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
        netports = self.get_network_ports()
        for port in netports:
            # try to connect to each "standard" ArduPilot UDP and TCP ports
            logging_debug(_("Trying network port %s"), port)
            err = self._register_and_try_connect(
                comport=mavutil.SerialPort(device=port, description=port),
                progress_callback=progress_callback,
                baudrate=self._baudrate,
                log_errors=False,
            )
            if err == "":
                return ""

        return _("No auto-detected ports responded. Please connect a flight controller and try again.")

    def _create_mavlink_connection(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        device: str,
        baudrate: int = 115200,
        timeout: int = 5,
        retries: int = 3,
        progress_callback: Union[None, Callable[[int, int], None]] = None,
    ) -> mavutil.mavlink_connection:  # pyright: ignore[reportGeneralTypeIssues]
        """
        Factory method for creating MAVLink connections.

        This method can be overridden in tests to inject mock connections.

        Args:
            device: Device string (serial port, TCP, UDP address, etc.)
            baudrate: Baud rate for serial connections
            timeout: Connection timeout in seconds
            retries: Number of connection retries
            progress_callback: Optional callback for progress updates

        Returns:
            mavutil.mavlink_connection: The MAVLink connection object

        """
        return self._mavlink_connection_factory.create(
            device=device,
            baudrate=baudrate,
            timeout=timeout,
            retries=retries,
            progress_callback=progress_callback,
        )

    def _detect_vehicles_from_heartbeats(self, timeout: int) -> dict[tuple[int, int], Any]:
        """
        Detect all vehicles by collecting HEARTBEAT messages within timeout period.

        Args:
            timeout: Time in seconds to wait for HEARTBEAT messages

        Returns:
            dict[tuple[int, int], Any]: Dictionary mapping (system_id, component_id) to HEARTBEAT message

        """
        start_time = time_time()
        detected_vehicles: dict[tuple[int, int], Any] = {}

        while time_time() - start_time < timeout:
            try:
                m = (
                    self.master.recv_match(  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue]
                        type="HEARTBEAT", blocking=False
                    )
                    if self.master
                    else None
                )
            except TypeError:
                # pymavlink internals may occasionally raise TypeError while
                # processing incoming messages (e.g. message dicts not fully
                # initialized). Treat this as a transient error and keep polling
                # until we either get a message or timeout.
                time_sleep(self.HEARTBEAT_POLL_DELAY)
                continue
            if m is None:
                time_sleep(self.HEARTBEAT_POLL_DELAY)
                continue
            sysid = m.get_srcSystem()
            compid = m.get_srcComponent()
            detected_vehicles[(sysid, compid)] = m
            logging_debug(_("Detected vehicle %u:%u (autopilot=%u, type=%u)"), sysid, compid, m.autopilot, m.type)

        return detected_vehicles

    def _select_supported_autopilot(self, detected_vehicles: dict[tuple[int, int], Any]) -> str:
        """
        Select a supported autopilot from detected vehicles.

        Args:
            detected_vehicles: Dictionary mapping (system_id, component_id) to HEARTBEAT message

        Returns:
            str: Error message if no supported autopilot found, empty string on success

        """
        if not detected_vehicles:
            return _("No MAVLink heartbeat received, connection failed.")

        for (sysid, compid), m in detected_vehicles.items():
            self.info.set_system_id_and_component_id(str(sysid), str(compid))
            logging_debug(
                _("Connection established with systemID %s, componentID %s."), self.info.system_id, self.info.component_id
            )
            self.info.set_autopilot(m.autopilot)
            if self.info.is_supported:
                msg = _("Autopilot type {self.info.autopilot}")
                logging_info(msg.format(**locals()))
                self.info.set_type(m.type)
                msg = _("Vehicle type: {self.info.mav_type} running {self.info.vehicle_type} firmware")
                logging_info(msg.format(**locals()))
                return ""  # Success
            msg = _("Unsupported autopilot type {self.info.autopilot}")
            logging_info(msg.format(**locals()))

        return _("No supported autopilots found")

    def _retrieve_autopilot_version_and_banner(self, timeout: int) -> str:
        """
        Request and process autopilot version and banner information.

        Args:
            timeout: Timeout in seconds for receiving messages

        Returns:
            str: Error message if processing failed, empty string on success

        """
        # Request banner and collect messages
        self._request_banner()
        banner_msgs = self._receive_banner_text()

        # Request AUTOPILOT_VERSION message
        self._request_message(mavutil.mavlink.MAVLINK_MSG_ID_AUTOPILOT_VERSION)
        m = (
            self.master.recv_match(  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue]
                type="AUTOPILOT_VERSION", blocking=True, timeout=timeout
            )
            if self.master
            else None
        )

        return self._process_autopilot_version(m, banner_msgs)

    def _request_banner(self) -> None:
        """Request banner information from the flight controller."""
        # https://mavlink.io/en/messages/ardupilotmega.html#MAV_CMD_DO_SEND_BANNER
        if self.master is not None:
            # Note: Don't wait for ACK here as banner requests are fire-and-forget
            # and we handle the response via STATUS_TEXT messages
            self.master.mav.command_long_send(  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue]
                self.master.target_system,  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue]
                self.master.target_component,  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue]
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

    def _receive_banner_text(self) -> list[str]:
        """
        Starts listening for STATUS_TEXT MAVLink messages.

        Returns:
            list[str]: List of banner text messages received

        """
        start_time = time_time()
        banner_msgs: list[str] = []
        while self.master:
            msg = self.master.recv_match(  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue]
                type="STATUSTEXT", blocking=False
            )
            if msg:
                if banner_msgs:
                    banner_msgs.append(msg.text)
                else:
                    banner_msgs = [msg.text]
            time_sleep(0.1)  # Sleep briefly to reduce CPU usage
            if time_time() - start_time > self.BANNER_RECEIVE_TIMEOUT:
                break  # Exit the loop if timeout elapsed
        return banner_msgs

    def _request_message(self, message_id: int) -> None:
        """
        Request a specific message from the flight controller.

        Args:
            message_id: MAVLink message ID to request

        """
        if self.master is not None:
            # Note: Don't wait for ACK here as this is used internally for autopilot version requests
            # and the response comes as the requested message itself
            # Convert system_id and component_id from string to int for MAVLink
            system_id = int(self.info.system_id) if self.info.system_id else 0
            component_id = int(self.info.component_id) if self.info.component_id else 0

            self.master.mav.command_long_send(  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue]
                system_id,
                component_id,
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

    def _get_connection_error_guidance(self, error: Exception, device: str) -> str:
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

    def _extract_chibios_version_from_banner(self, banner_msgs: list[str]) -> tuple[str, Optional[int]]:
        """
        Extract ChibiOS version and its index from banner messages.

        Args:
            banner_msgs: List of banner messages received from flight controller

        Returns:
            tuple[str, Optional[int]]: (os_custom_version, os_custom_version_index)
                os_custom_version is the extracted ChibiOS version string
                os_custom_version_index is the index where ChibiOS version was found, or None

        """
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

        return os_custom_version, os_custom_version_index

    def _extract_firmware_type_from_banner(self, banner_msgs: list[str], os_custom_version_index: Optional[int]) -> str:
        """
        Extract firmware type from banner messages.

        Args:
            banner_msgs: List of banner messages received from flight controller
            os_custom_version_index: Index where ChibiOS version was found, or None

        Returns:
            str: The extracted firmware type (e.g., "ArduCopter", "ArduPlane")

        """
        firmware_type = ""

        # Try to extract from message after ChibiOS version
        if os_custom_version_index is not None and os_custom_version_index + 1 < len(banner_msgs):
            firmware_type_banner_substrings = banner_msgs[os_custom_version_index + 1].split(" ")
            if len(firmware_type_banner_substrings) >= 3:
                firmware_type = firmware_type_banner_substrings[0]

        # Fallback: try first banner message (for SITL or systems without ChibiOS)
        elif banner_msgs and not firmware_type:
            firmware_type_banner_substrings = banner_msgs[0].split(" ")
            if len(firmware_type_banner_substrings) >= 1 and firmware_type_banner_substrings[0].strip():
                firmware_type = firmware_type_banner_substrings[0].strip()

        return firmware_type

    def _populate_flight_controller_info(self, m: MAVLink_autopilot_version_message) -> None:
        """
        Populate flight controller info from AUTOPILOT_VERSION message.

        Args:
            m: The AUTOPILOT_VERSION MAVLink message

        """
        self.info.set_capabilities(m.capabilities)
        self.info.set_flight_sw_version(m.flight_sw_version)
        self.info.set_usb_vendor_and_product_ids(m.vendor_id, m.product_id)  # must be done before set_board_version()
        self.info.set_board_version(m.board_version)
        self.info.set_flight_custom_version(m.flight_custom_version)
        self.info.set_os_custom_version(m.os_custom_version)

    def _process_autopilot_version(self, m: Optional[MAVLink_autopilot_version_message], banner_msgs: list[str]) -> str:
        """
        Process AUTOPILOT_VERSION message and banner messages to extract flight controller info.

        Args:
            m: The AUTOPILOT_VERSION MAVLink message, or None if not received
            banner_msgs: List of banner messages received from flight controller

        Returns:
            str: Error message if processing failed, empty string on success

        """
        if m is None:
            return _(
                "No AUTOPILOT_VERSION MAVLink message received, connection failed.\n"
                "Only ArduPilot versions newer than 4.3.8 are supported.\n"
                "Make sure parameter SERIAL0_PROTOCOL is set to 2"
            )

        # Populate basic flight controller info from AUTOPILOT_VERSION message
        self._populate_flight_controller_info(m)

        # Extract ChibiOS version from banner messages
        _os_custom_version, os_custom_version_index = self._extract_chibios_version_from_banner(banner_msgs)

        # Extract firmware type from banner messages
        firmware_type = self._extract_firmware_type_from_banner(banner_msgs, os_custom_version_index)

        # Update firmware type if found and different from AUTOPILOT_VERSION
        if firmware_type and firmware_type != self.info.firmware_type:
            logging_debug(
                _("FC firmware type mismatch: %s (BANNER) != %s (AUTOPILOT_VERSION)"), firmware_type, self.info.firmware_type
            )
            self.info.firmware_type = firmware_type  # force the one from the banner because it is more reliable

        return ""

    @staticmethod
    @no_type_check
    def get_serial_ports() -> list[ListPortInfo]:  # pyright: ignore[reportGeneralTypeIssues]
        """
        Get all available serial ports.

        Returns:
            list[ListPortInfo]: List of available serial ports

        """
        return list(serial.tools.list_ports.comports())

    def get_network_ports(self) -> list[str]:
        """
        Get available network ports.

        Returns:
            list[str]: List of network connection strings

        """
        return self._network_ports

    # pylint: disable=duplicate-code
    def _auto_detect_serial(self) -> list[mavutil.SerialPort]:
        """
        Auto-detect serial ports with connected flight controllers.

        Returns:
            list[mavutil.SerialPort]: List of detected serial ports

        """
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
            for connection in self._connection_tuples
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

    def create_connection_with_retry(  # pylint: disable=too-many-arguments, too-many-positional-arguments
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
        if self.comport is None or self.comport.device == DEVICE_FC_PARAM_FROM_FILE:
            # will read parameters from a params.param file instead of a from a flight controller
            return ""
        if self.comport.device.startswith("udp") or self.comport.device.startswith("tcp"):
            logging_info(_("Will connect to %s"), self.comport.device)
        else:
            logging_info(_("Will connect to %s @ %u baud"), self.comport.device, baudrate)
        try:
            # Create the connection
            self.master = self._create_mavlink_connection(
                device=self.comport.device,
                baudrate=baudrate,
                timeout=timeout,
                retries=retries,
                progress_callback=progress_callback,
            )
            logging_debug(_("Waiting for MAVLink heartbeats..."))
            if not self.master:
                msg = f"Failed to create mavlink connect to {self.comport.device}"
                raise ConnectionError(msg)

            # Detect all vehicles from HEARTBEAT messages
            detected_vehicles = self._detect_vehicles_from_heartbeats(timeout)

            # Select a supported autopilot
            error = self._select_supported_autopilot(detected_vehicles)
            if error:
                return error

            # Retrieve autopilot version and banner information
            return self._retrieve_autopilot_version_and_banner(timeout)

        except (ConnectionError, SerialException, PermissionError, ConnectionRefusedError) as e:
            if log_errors:
                logging_warning(_("Connection failed: %s"), e)
                logging_error(_("Failed to connect after %d attempts."), retries)
            error_message = str(e)
            guidance = self._get_connection_error_guidance(e, self.comport.device if self.comport else "")
            if guidance:
                error_message = f"{error_message}\n\n{guidance}"
            return error_message

    def get_connection_tuples(self) -> list[tuple[str, str]]:
        """
        Get list of available connection strings as (device, description) tuples.

        Returns:
            list[tuple[str, str]]: List of (device, description) tuples

        """
        return self._connection_tuples

    @property
    def comport_device(self) -> str:
        """Get the device string of the current comport."""
        if self.comport is None:
            return ""
        return str(getattr(self.comport, "device", ""))

    @property
    def baudrate(self) -> int:
        """Get the default baud rate for serial connections."""
        return self._baudrate

    def set_master_for_testing(
        self,
        master: Optional[mavutil.mavlink_connection],  # pyright: ignore[reportGeneralTypeIssues]
    ) -> None:
        """
        Set the MAVLink connection for testing purposes.

        WARNING: This is a testing-only method. Do not use in production code.
        Use connect() instead for proper connection establishment.

        This method properly initializes the connection state including setting
        the master connection object. Unlike direct property assignment, this
        ensures consistent state initialization.

        Args:
            master: The MAVLink connection object or None

        """
        self.master = master
        # If setting to None, also clear related state
        if master is None:
            self.comport = None
