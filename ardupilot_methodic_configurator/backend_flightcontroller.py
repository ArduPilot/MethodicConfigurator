"""
Flight controller interface.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from argparse import ArgumentParser
from logging import debug as logging_debug
from logging import error as logging_error
from logging import info as logging_info
from logging import warning as logging_warning
from os import path as os_path
from pathlib import Path
from time import sleep as time_sleep
from typing import TYPE_CHECKING, Any, Callable, Optional, Union, cast

from pymavlink import mavutil
from serial.tools.list_ports_common import ListPortInfo

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.argparse_check_range import CheckRange
from ardupilot_methodic_configurator.backend_flightcontroller_commands import FlightControllerCommands
from ardupilot_methodic_configurator.backend_flightcontroller_connection import (
    DEFAULT_BAUDRATE,
    DEVICE_FC_PARAM_FROM_FILE,
    SUPPORTED_BAUDRATES,
    FlightControllerConnection,
)
from ardupilot_methodic_configurator.backend_flightcontroller_files import FlightControllerFiles
from ardupilot_methodic_configurator.backend_flightcontroller_params import FlightControllerParams
from ardupilot_methodic_configurator.backend_flightcontroller_protocols import (
    FlightControllerCommandsProtocol,
    FlightControllerConnectionProtocol,
    FlightControllerFilesProtocol,
    FlightControllerParamsProtocol,
    MavlinkConnection,
)
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo
from ardupilot_methodic_configurator.data_model_par_dict import ParDict

if TYPE_CHECKING:
    from pymavlink.dialects.v20.ardupilotmega import MAVLink_autopilot_version_message

DEFAULT_REBOOT_TIME: int = 7

# Re-export constants for backwards compatibility
__all__ = [
    "DEFAULT_BAUDRATE",
    "DEFAULT_REBOOT_TIME",
    "DEVICE_FC_PARAM_FROM_FILE",
    "SUPPORTED_BAUDRATES",
    "FlightController",
    "FlightControllerInfo",
    "ParDict",
]


class FlightController:  # pylint: disable=too-many-public-methods
    """
    Facade for flight controller operations using delegation pattern.

    This class delegates to specialized managers for different concerns:
    - Connection operations → FlightControllerConnection (connection_manager)
    - Parameter operations → FlightControllerParams (params_manager)
    - Command execution → FlightControllerCommands (commands_manager)
    - File operations → FlightControllerFiles (files_manager)

    The connection manager is the single source of truth for connection state
    (master, comport, info). Other managers query the connection manager for
    current state rather than caching it.

    Properties (delegated to managers):
        master: MAVLink connection object (delegates to connection_manager)
        comport: Current serial/network port (delegates to connection_manager)
        comport_device: Device string of current port (delegates to connection_manager)
        info: Flight controller metadata (delegates to connection_manager)
        fc_parameters: Parameter dictionary (delegates to params_manager)
        reboot_time: Time to wait after reboot before reconnecting
        baudrate: Default baud rate for serial connections

    Note on Manager Creation Order:
        Managers must be created in this order due to dependencies:
        1. FlightControllerInfo (shared state object)
        2. FlightControllerConnection (owns master, comport, info)
        3. FlightControllerParams (depends on connection_manager)
        4. FlightControllerCommands (depends on params_manager and connection_manager)
        5. FlightControllerFiles (depends on connection_manager)

    """

    def __init__(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        reboot_time: int = DEFAULT_REBOOT_TIME,
        baudrate: int = DEFAULT_BAUDRATE,
        network_ports: Optional[list[str]] = None,
        info: Optional[FlightControllerInfo] = None,
        connection_manager: Optional[FlightControllerConnectionProtocol] = None,
        params_manager: Optional[FlightControllerParamsProtocol] = None,
        commands_manager: Optional[FlightControllerCommandsProtocol] = None,
        files_manager: Optional[FlightControllerFilesProtocol] = None,
    ) -> None:
        """
        Initialize the FlightController communication object.

        Args:
            reboot_time: Time to wait after reboot before reconnecting
            baudrate: Default baud rate for serial connections
            network_ports: Optional list of network ports to try
            info: Optional FlightControllerInfo instance (for dependency injection in tests)
            connection_manager: Optional connection manager (for dependency injection in tests)
            params_manager: Optional params manager (for dependency injection in tests)
            commands_manager: Optional commands manager (for dependency injection in tests)
            files_manager: Optional files manager (for dependency injection in tests)

        Note:
            If not provided, managers are created in dependency order:
            info → connection_manager → params_manager → commands_manager → files_manager
            All managers require their dependencies to be created first.

        """
        # warn people about ModemManager which interferes badly with ArduPilot
        if os_path.exists("/usr/sbin/ModemManager"):
            logging_warning(_("You should uninstall ModemManager as it conflicts with ArduPilot"))

        self._reboot_time = reboot_time
        self._network_ports = network_ports if network_ports is not None else FlightControllerConnection.DEFAULT_NETWORK_PORTS

        # Component managers (delegation pattern with dependency injection support)
        # If managers are provided via DI, use them; otherwise create default instances
        # Connection manager is created first as it owns master, comport, and info (accessed via properties)
        # Share the same FlightControllerInfo instance across all managers
        _info = info or FlightControllerInfo()
        self._connection_manager: FlightControllerConnectionProtocol = connection_manager or FlightControllerConnection(
            info=_info, baudrate=baudrate, network_ports=self._network_ports
        )

        self._params_manager: FlightControllerParamsProtocol = params_manager or FlightControllerParams(
            connection_manager=self._connection_manager,
            fc_parameters=None,  # Let params_manager create its own fc_parameters dict
        )

        self._commands_manager: FlightControllerCommandsProtocol = cast(
            "FlightControllerCommandsProtocol",
            commands_manager
            or FlightControllerCommands(
                params_manager=self._params_manager,
                connection_manager=self._connection_manager,
            ),
        )

        self._files_manager: FlightControllerFilesProtocol = files_manager or FlightControllerFiles(
            connection_manager=self._connection_manager
        )

        # Discover available connections
        self.discover_connections()

    @property
    def master(self) -> Optional[MavlinkConnection]:
        """Get the MAVLink connection - delegates to connection manager."""
        return self._connection_manager.master

    def set_master_for_testing(self, value: Optional[MavlinkConnection]) -> None:
        """
        Set the MAVLink connection - FOR TESTING PURPOSES ONLY.

        **WARNING: This is a testing-only method.**

        This method delegates to the connection manager's set_master_for_testing()
        which properly initializes connection state. While still a testing hack,
        this is better than direct property assignment as it allows the connection
        manager to maintain state consistency.

        **NEVER use this method in production code - use connect() instead.**

        Args:
            value: The MAVLink connection object or None

        Note:
            See ARCHITECTURE.md for details on testing patterns and architectural
            violations.

        """
        self._connection_manager.set_master_for_testing(value)

    @property
    def comport(self) -> Union[mavutil.SerialPort, ListPortInfo, None]:
        """Get the current comport - delegates to connection manager."""
        return self._connection_manager.comport

    @property
    def comport_device(self) -> str:
        """Get the current comport device string - delegates to connection manager (single source of truth)."""
        return self._connection_manager.comport_device

    @property
    def info(self) -> FlightControllerInfo:
        """
        Get flight controller info - delegates to connection manager (single source of truth).

        Note: Connection manager is the sole mutator of this object to maintain consistency.
        """
        return self._connection_manager.info

    @property
    def reboot_time(self) -> int:
        """Get the reboot time setting."""
        return self._reboot_time

    @property
    def baudrate(self) -> int:
        """Get the baudrate setting - delegates to connection manager."""
        return self._connection_manager.baudrate

    @property
    def PARAM_FETCH_POLL_DELAY(self) -> float:  # noqa: N802 # pylint: disable=invalid-name
        """Get parameter fetch poll delay - delegates to params manager."""
        return self._params_manager.PARAM_FETCH_POLL_DELAY

    @property
    def BATTERY_STATUS_CACHE_TIME(self) -> float:  # noqa: N802 # pylint: disable=invalid-name
        """Get battery status cache time - delegates to commands manager."""
        return self._commands_manager.BATTERY_STATUS_CACHE_TIME

    @property
    def BATTERY_STATUS_TIMEOUT(self) -> float:  # noqa: N802 # pylint: disable=invalid-name
        """Get battery status timeout - delegates to commands manager."""
        return self._commands_manager.BATTERY_STATUS_TIMEOUT

    @property
    def COMMAND_ACK_TIMEOUT(self) -> float:  # noqa: N802 # pylint: disable=invalid-name
        """Get command acknowledgment timeout - delegates to commands manager."""
        return self._commands_manager.COMMAND_ACK_TIMEOUT

    @property
    def fc_parameters(self) -> dict[str, float]:
        """Get flight controller parameters - delegates to params manager."""
        return self._params_manager.fc_parameters

    @fc_parameters.setter
    def fc_parameters(self, value: dict[str, float]) -> None:
        """Set flight controller parameters - delegates to params manager."""
        self._params_manager.fc_parameters = value

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
        if self.master is None:
            logging_warning(_("Cannot reset flight controller: not connected"))
            return ""
        # Issue a reset
        # Type ignore needed because MavlinkConnection is a Union including object fallback
        self.master.reboot_autopilot()  # type: ignore[union-attr]
        logging_info(_("Reset command sent to ArduPilot."))
        time_sleep(0.3)  # Short delay for command to be sent

        self.disconnect()

        current_step = 0

        if extra_sleep_time is None or extra_sleep_time < 0:
            extra_sleep_time = 0

        sleep_time = self._reboot_time + extra_sleep_time

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
        return self.create_connection_with_retry(connection_progress_callback, baudrate=self.baudrate)

    def discover_connections(self) -> None:
        """Discover available connections - delegates to connection manager."""
        self._connection_manager.discover_connections()

    def disconnect(self) -> None:
        """Close the connection to the flight controller - delegates to connection manager."""
        self._connection_manager.disconnect()
        # Clear parameter cache via params manager
        self._params_manager.clear_parameters()

    def add_connection(self, connection_string: str) -> bool:
        """Add a new connection to the list of available connections - delegates to connection manager."""
        return self._connection_manager.add_connection(connection_string)

    # Testing-only methods (protected methods exposed for SITL integration tests)
    def _detect_vehicles_from_heartbeats(self, timeout: int) -> dict[tuple[int, int], Any]:
        """Detect vehicles from heartbeats - delegates to connection manager (testing only)."""
        return self._connection_manager._detect_vehicles_from_heartbeats(timeout)  # noqa: SLF001 # pylint: disable=protected-access

    def _extract_firmware_type_from_banner(self, banner_msgs: list[str], os_custom_version_index: Optional[int]) -> str:
        """Extract firmware type from banner - delegates to connection manager (testing only)."""
        return self._connection_manager._extract_firmware_type_from_banner(  # noqa: SLF001 # pylint: disable=protected-access
            banner_msgs, os_custom_version_index
        )

    def _extract_chibios_version_from_banner(self, banner_msgs: list[str]) -> tuple[str, Optional[int]]:
        """Extract ChibiOS version from banner - delegates to connection manager (testing only)."""
        return self._connection_manager._extract_chibios_version_from_banner(banner_msgs)  # noqa: SLF001 # pylint: disable=protected-access

    def _select_supported_autopilot(self, detected_vehicles: dict[tuple[int, int], Any]) -> str:
        """Select supported autopilot from detected vehicles - delegates to connection manager (testing only)."""
        return self._connection_manager._select_supported_autopilot(detected_vehicles)  # noqa: SLF001 # pylint: disable=protected-access

    def _populate_flight_controller_info(self, m: "MAVLink_autopilot_version_message") -> None:
        """Populate flight controller info from autopilot version - delegates to connection manager (testing only)."""
        self._connection_manager._populate_flight_controller_info(m)  # noqa: SLF001 # pylint: disable=protected-access

    def _retrieve_autopilot_version_and_banner(self, timeout: int) -> str:
        """Retrieve autopilot version and banner - delegates to connection manager (testing only)."""
        return self._connection_manager._retrieve_autopilot_version_and_banner(timeout)  # noqa: SLF001 # pylint: disable=protected-access

    def connect(
        self,
        device: str,
        progress_callback: Union[None, Callable[[int, int], None]] = None,
        log_errors: bool = True,
        baudrate: Optional[int] = None,
    ) -> str:
        """
        Establishes a connection to the FlightController - delegates to connection manager.

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
        return self._connection_manager.connect(
            device=device,
            progress_callback=progress_callback,
            log_errors=log_errors,
            baudrate=baudrate,
        )

    def create_connection_with_retry(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        progress_callback: Union[None, Callable[[int, int], None]],
        retries: int = 3,
        timeout: int = 5,
        baudrate: int = DEFAULT_BAUDRATE,
        log_errors: bool = True,
    ) -> str:
        """
        Attempts to create a connection to the flight controller - delegates to connection manager.

        Args:
            progress_callback: A callback function to report progress
            retries: The number of retries before giving up
            timeout: The timeout in seconds for each connection attempt
            baudrate: The baud rate for the connection
            log_errors: Whether to log errors

        Returns:
            str: An error message if connection fails, otherwise empty string

        """
        return self._connection_manager.create_connection_with_retry(
            progress_callback=progress_callback,
            retries=retries,
            timeout=timeout,
            baudrate=baudrate,
            log_errors=log_errors,
        )

    @staticmethod
    def get_serial_ports() -> list[ListPortInfo]:
        """Get all available serial ports - delegates to connection manager."""
        return FlightControllerConnection.get_serial_ports()  # type: ignore[no-any-return]

    def get_network_ports(self) -> list[str]:
        """Get all available network ports - delegates to connection manager."""
        return self._connection_manager.get_network_ports()

    def get_connection_tuples(self) -> list[tuple[str, str]]:
        """Get all available connections - delegates to connection manager."""
        return self._connection_manager.get_connection_tuples()

    # Parameters interface - Delegated to params manager

    def download_params(
        self,
        progress_callback: Union[None, Callable[[int, int], None]] = None,
        parameter_values_filename: Optional[Path] = None,
        parameter_defaults_filename: Optional[Path] = None,
    ) -> tuple[dict[str, float], ParDict]:
        """Download all parameters from flight controller - delegates to params manager."""
        params, defaults = self._params_manager.download_params(
            progress_callback, parameter_values_filename, parameter_defaults_filename
        )
        # params_manager updates its fc_parameters internally, which we access via property
        return params, defaults

    def set_param(self, param_name: str, param_value: float) -> tuple[bool, str]:
        """Set a parameter on the flight controller - delegates to params manager."""
        return self._params_manager.set_param(param_name, param_value)

    def fetch_param(self, param_name: str, timeout: int = 5) -> Optional[float]:
        """Fetch a parameter from the flight controller - delegates to params manager."""
        return self._params_manager.fetch_param(param_name, timeout)

    def reset_all_parameters_to_default(self) -> tuple[bool, str]:
        """Reset all parameters to their factory default values - delegates to commands manager."""
        return self._commands_manager.reset_all_parameters_to_default()

    # Motor Test Functionality - Delegated to commands manager

    def test_motor(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self, test_sequence_nr: int, motor_letters: str, motor_output_nr: int, throttle_percent: int, timeout_seconds: int
    ) -> tuple[bool, str]:
        """Test a specific motor - delegates to commands manager."""
        return self._commands_manager.test_motor(
            test_sequence_nr, motor_letters, motor_output_nr, throttle_percent, timeout_seconds
        )

    def test_all_motors(self, nr_of_motors: int, throttle_percent: int, timeout_seconds: int) -> tuple[bool, str]:
        """Test all motors simultaneously - delegates to commands manager."""
        return self._commands_manager.test_all_motors(nr_of_motors, throttle_percent, timeout_seconds)

    def test_motors_in_sequence(
        self, start_motor: int, motor_count: int, throttle_percent: int, timeout_seconds: int
    ) -> tuple[bool, str]:
        """Test motors in sequence - delegates to commands manager."""
        return self._commands_manager.test_motors_in_sequence(start_motor, motor_count, throttle_percent, timeout_seconds)

    def stop_all_motors(self) -> tuple[bool, str]:
        """Emergency stop for all motors - delegates to commands manager."""
        return self._commands_manager.stop_all_motors()

    def request_periodic_battery_status(self, interval_microseconds: int = 1000000) -> tuple[bool, str]:
        """Request periodic BATTERY_STATUS messages - delegates to commands manager."""
        return self._commands_manager.request_periodic_battery_status(interval_microseconds)

    def get_battery_status(self) -> tuple[Union[tuple[float, float], None], str]:
        """Get current battery voltage and current - delegates to commands manager."""
        return self._commands_manager.get_battery_status()

    def get_voltage_thresholds(self) -> tuple[float, float]:
        """Get battery voltage thresholds - delegates to commands manager."""
        return self._commands_manager.get_voltage_thresholds()

    def is_battery_monitoring_enabled(self) -> bool:
        """Check if battery monitoring is enabled - delegates to commands manager."""
        return self._commands_manager.is_battery_monitoring_enabled()

    # MAVLink Signing Functionality

    def setup_signing(
        self,
        key: bytes,
        sign_outgoing: bool = True,
        allow_unsigned_in: bool = True,
        initial_timestamp: int = 0,
        link_id: int = 0,
    ) -> tuple[bool, str]:
        """
        Set up MAVLink 2.0 message signing for secure communication.

        This enables HMAC-SHA256 signing of MAVLink messages to provide
        authentication and prevent message tampering/injection.

        Args:
            key: 32-byte signing key (256-bit) for HMAC-SHA256
            sign_outgoing: Whether to sign outgoing messages (default: True)
            allow_unsigned_in: Whether to accept unsigned incoming messages (default: True)
            initial_timestamp: Initial timestamp for replay protection (default: 0 = use current time)
            link_id: Link ID for signing (0-255, default: 0)

        Returns:
            tuple[bool, str]: (success, error_message)
                - success is True if signing was set up successfully
                - error_message is empty on success or contains error description

        Raises:
            ValueError: If key is not 32 bytes or link_id is out of range

        Note:
            MAVLink signing provides authentication (not encryption).
            Messages are still sent in plaintext but include a cryptographic
            signature to verify authenticity and detect tampering.

        """
        if self.master is None:
            error_msg = _("No flight controller connection available for signing setup")
            logging_warning(error_msg)
            return False, error_msg

        if len(key) != 32:
            msg = f"Signing key must be 32 bytes, got {len(key)} bytes"
            raise ValueError(msg)

        if not 0 <= link_id <= 255:
            msg = f"link_id must be between 0 and 255, got {link_id}"
            raise ValueError(msg)

        try:
            # Set up the signing state on the MAVLink connection
            # pymavlink's mavlink_connection supports signing setup
            # Type ignore needed because MavlinkConnection is a Union including object fallback
            self.master.setup_signing(  # type: ignore[union-attr]
                key,
                sign_outgoing=sign_outgoing,
                allow_unsigned_callback=self._unsigned_callback if allow_unsigned_in else None,
                initial_timestamp=initial_timestamp,
                link_id=link_id,
            )

            logging_info(
                _("MAVLink signing configured: sign_outgoing=%(sign)s, allow_unsigned=%(unsigned)s"),
                {"sign": sign_outgoing, "unsigned": allow_unsigned_in},
            )
            return True, ""

        except AttributeError:
            error_msg = _("MAVLink signing not supported by this pymavlink version")
            logging_error(error_msg)
            return False, error_msg
        except Exception as exc:  # pylint: disable=broad-except
            error_msg = _("Failed to set up MAVLink signing: %(error)s") % {"error": str(exc)}
            logging_error(error_msg)
            return False, error_msg

    def _unsigned_callback(self, msg: object) -> bool:
        """
        Callback to handle unsigned incoming messages when signing is enabled.

        This callback is invoked for each unsigned message when signing is
        configured with allow_unsigned_in=True. It allows filtering which
        unsigned messages to accept.

        Args:
            msg: The unsigned MAVLink message

        Returns:
            bool: True to accept the message, False to reject it

        Note:
            By default, this accepts all unsigned messages (permissive mode).
            Override or modify this behavior for stricter security policies.

        """
        # Log unsigned messages for security monitoring
        msg_type = getattr(msg, "get_type", lambda: "unknown")()
        logging_debug(_("Received unsigned MAVLink message: %(type)s"), {"type": msg_type})

        # Accept all unsigned messages by default (permissive mode)
        # This allows communication during signing setup and transition periods
        return True

    def disable_signing(self) -> tuple[bool, str]:
        """
        Disable MAVLink message signing.

        This removes signing configuration and returns to unsigned communication.

        Returns:
            tuple[bool, str]: (success, error_message)
                - success is True if signing was disabled successfully
                - error_message is empty on success or contains error description

        """
        if self.master is None:
            error_msg = _("No flight controller connection available")
            logging_warning(error_msg)
            return False, error_msg

        try:
            # Disable signing by passing None as key
            # Type ignore needed because MavlinkConnection is a Union including object fallback
            self.master.setup_signing(None, sign_outgoing=False, allow_unsigned_callback=None)  # type: ignore[union-attr]
            logging_info(_("MAVLink signing disabled"))
            return True, ""
        except AttributeError:
            error_msg = _("MAVLink signing not supported by this pymavlink version")
            logging_error(error_msg)
            return False, error_msg
        except Exception as exc:  # pylint: disable=broad-except
            error_msg = _("Failed to disable MAVLink signing: %(error)s") % {"error": str(exc)}
            logging_error(error_msg)
            return False, error_msg

    def get_signing_status(self) -> dict[str, object]:
        """
        Get the current MAVLink signing status.

        Returns:
            dict: Signing status with keys:
                - enabled: Whether signing is configured
                - sign_outgoing: Whether outgoing messages are signed
                - allow_unsigned: Whether unsigned messages are accepted
                - link_id: Current link ID (if signing enabled)
                - message: Human-readable status message

        """
        status: dict[str, object] = {
            "enabled": False,
            "sign_outgoing": False,
            "allow_unsigned": True,
            "link_id": 0,
            "message": _("No connection"),
        }

        if self.master is None:
            return status

        try:
            # Check if signing is set up on the MAVLink connection
            # Type ignore needed because MavlinkConnection is a Union including object fallback
            mav = self.master.mav  # type: ignore[union-attr]
            if hasattr(mav, "signing") and mav.signing is not None:
                signing = mav.signing
                status["enabled"] = True
                status["sign_outgoing"] = getattr(signing, "sign_outgoing", False)
                status["allow_unsigned"] = getattr(signing, "allow_unsigned_callback", None) is not None
                status["link_id"] = getattr(signing, "link_id", 0)
                status["message"] = _("Signing enabled")
            else:
                status["message"] = _("Signing not configured")

        except Exception as exc:  # pylint: disable=broad-except
            logging_debug(_("Error getting signing status: %(error)s"), {"error": str(exc)})
            status["message"] = _("Error: %(error)s") % {"error": str(exc)}

        return status

    def get_frame_info(self) -> tuple[int, int]:
        """Get frame class and frame type - delegates to commands manager."""
        return self._commands_manager.get_frame_info()

    # File operations - Delegated to files manager

    def upload_file(
        self, local_filename: str, remote_filename: str, progress_callback: Union[None, Callable[[int, int], None]] = None
    ) -> bool:
        """Upload a file to the flight controller - delegates to files manager."""
        return self._files_manager.upload_file(local_filename, remote_filename, progress_callback)

    def download_last_flight_log(
        self, local_filename: str, progress_callback: Union[None, Callable[[int, int], None]] = None
    ) -> bool:
        """Download the last flight log from the flight controller - delegates to files manager."""
        return self._files_manager.download_last_flight_log(local_filename, progress_callback)

    # Static methods and properties

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
                'If set to "none" no connection is made. '
                'If set to "file" the file params.param is used. '
                "Default is autodetection"
            ),
        ).completer = lambda **_: FlightController.get_serial_ports()  # pyright: ignore[reportAttributeAccessIssue]
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
