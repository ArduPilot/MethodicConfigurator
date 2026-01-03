"""
Protocol interfaces for flight controller component managers.

These protocols define the contracts between the main FlightController class
and its component managers, enabling dependency injection and better testability.

Type Checking Pattern:
    To avoid circular imports, implementations should import these protocols
    using TYPE_CHECKING guard:

        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from ardupilot_methodic_configurator.backend_flightcontroller_protocols import (
                FlightControllerConnectionProtocol,
            )

    This allows type hints to reference the protocol without runtime import,
    preventing circular dependency issues.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, Protocol, Union

import serial.tools.list_ports_common

from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo
from ardupilot_methodic_configurator.data_model_par_dict import ParDict

# Type alias for MAVLink connection to avoid type checker issues
# pymavlink.mavutil.mavlink_connection is actually a function that returns various connection types
# We define MavlinkConnection as a protocol-like type to represent any MAVLink connection object
if TYPE_CHECKING:
    # During type checking, import the actual mavutil module for better type hints
    from pymavlink import mavutil
    from pymavlink.dialects.v20.ardupilotmega import MAVLink_autopilot_version_message

    # Use a union of known connection types for better type safety
    # Note: mavutil.mavlink_connection() returns different types based on the connection string
    MavlinkConnection = Union[
        mavutil.mavserial,
        mavutil.mavudp,
        mavutil.mavtcp,
        mavutil.mavtcpin,
        mavutil.mavmcast,
        object,  # Fallback for other connection types
    ]
else:
    # At runtime, we don't need the actual types
    from pymavlink import mavutil

    MavlinkConnection = object


class FlightControllerConnectionProtocol(Protocol):
    """
    Protocol for flight controller connection management.

    The connection manager is the single source of truth for:
    - master: MAVLink connection object
    - comport: Current serial/network port
    - info: Flight controller metadata (connection manager is sole mutator)

    Dependencies:
        Required at construction:
            - info: FlightControllerInfo (shared state, can be provided or created)
            - baudrate: int (default baud rate for serial connections)
            - network_ports: list[str] (list of network ports to try)
    """

    @property
    def master(self) -> Optional[MavlinkConnection]:
        """Get the current MAVLink connection object."""

    @property
    def info(self) -> FlightControllerInfo:  # pyright: ignore[reportInvalidTypeForm]
        """Get flight controller information (connection manager is sole mutator)."""
        ...  # pylint: disable=unnecessary-ellipsis

    @property
    def comport(self) -> Union[mavutil.SerialPort, serial.tools.list_ports_common.ListPortInfo, None]:
        """Get the current communication port."""

    @property
    def comport_device(self) -> str: ...

    @property
    def baudrate(self) -> int:
        """Get the default baud rate for serial connections."""
        ...  # pylint: disable=unnecessary-ellipsis

    def discover_connections(self) -> None: ...

    def disconnect(self) -> None: ...

    def add_connection(self, connection_string: str) -> bool: ...

    def connect(
        self,
        device: str,
        progress_callback: Union[None, Callable[[int, int], None]],
        log_errors: bool,
        baudrate: Optional[int],
    ) -> str: ...

    def create_connection_with_retry(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        progress_callback: Union[None, Callable[[int, int], None]],
        retries: int,
        timeout: int,
        baudrate: int,
        log_errors: bool,
    ) -> str: ...

    def get_serial_ports(self) -> list[serial.tools.list_ports_common.ListPortInfo]:
        """Get all available serial ports."""
        ...  # pylint: disable=unnecessary-ellipsis

    def get_network_ports(self) -> list[str]:
        """Get all available network ports."""
        ...  # pylint: disable=unnecessary-ellipsis

    def get_connection_tuples(self) -> list[tuple[str, str]]: ...

    def set_master_for_testing(self, master: Optional[MavlinkConnection]) -> None:
        """
        Set the MAVLink connection for testing purposes.

        WARNING: This is a testing-only method that properly initializes connection state.
        Do not use in production code - use connect() instead.

        Args:
            master: The MAVLink connection object or None

        """

    def _detect_vehicles_from_heartbeats(self, timeout: int) -> dict[tuple[int, int], Any]: ...

    def _extract_firmware_type_from_banner(self, banner_msgs: list[str], os_custom_version_index: Optional[int]) -> str: ...

    def _extract_chibios_version_from_banner(self, banner_msgs: list[str]) -> tuple[str, Optional[int]]: ...

    def _select_supported_autopilot(self, detected_vehicles: dict[tuple[int, int], Any]) -> str: ...

    def _populate_flight_controller_info(self, m: "MAVLink_autopilot_version_message") -> None: ...

    def _retrieve_autopilot_version_and_banner(self, timeout: int) -> str: ...


class FlightControllerParamsProtocol(Protocol):
    """
    Protocol for flight controller parameter operations.

    Dependencies:
        Required at construction:
            - connection_manager: FlightControllerConnectionProtocol (to access master, info, comport_device)
        Optional at construction:
            - fc_parameters: dict[str, float] (shared parameter dictionary, created if not provided)
    """

    # Class constant exposed as property for backward compatibility
    PARAM_FETCH_POLL_DELAY: float

    @property
    def fc_parameters(self) -> dict[str, float]:
        """Get the parameter dictionary."""
        ...  # pylint: disable=unnecessary-ellipsis

    @fc_parameters.setter
    def fc_parameters(self, value: dict[str, float]) -> None:
        """Set the parameter dictionary."""

    def download_params(
        self,
        progress_callback: Union[None, Callable[[int, int], None]],
        parameter_values_filename: Optional[Path],
        parameter_defaults_filename: Optional[Path],
    ) -> tuple[dict[str, float], ParDict]: ...

    def set_param(self, param_name: str, param_value: float) -> tuple[bool, str]: ...

    def fetch_param(self, param_name: str, timeout: int) -> Optional[float]: ...

    def get_param(self, param_name: str, default: float = 0.0) -> float: ...

    def clear_parameters(self) -> None: ...


class FlightControllerCommandsProtocol(Protocol):
    """
    Protocol for flight controller command execution.

    Note: Commands manager queries params_manager for parameter values
    rather than caching references, ensuring fresh data.

    Dependencies:
        Required at construction:
            - params_manager: FlightControllerParamsProtocol (to query parameter values)
            - connection_manager: FlightControllerConnectionProtocol (to access master)
    """

    # Class constants exposed for testing
    COMMAND_ACK_TIMEOUT: float
    BATTERY_STATUS_CACHE_TIME: float
    BATTERY_STATUS_TIMEOUT: float

    def send_command_and_wait_ack(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        command: int,
        param1: float,
        param2: float,
        param3: float,
        param4: float,
        param5: float,
        param6: float,
        param7: float,
        timeout: float,
    ) -> tuple[bool, str]: ...

    def reset_all_parameters_to_default(self) -> tuple[bool, str]: ...

    def test_motor(  # pylint: disable=too-many-arguments, too-many-positional-arguments
        self, test_sequence_nr: int, motor_letters: str, motor_output_nr: int, throttle_percent: int, timeout_seconds: int
    ) -> tuple[bool, str]: ...

    def test_all_motors(self, nr_of_motors: int, throttle_percent: int, timeout_seconds: int) -> tuple[bool, str]: ...

    def test_motors_in_sequence(
        self, start_motor: int, motor_count: int, throttle_percent: int, timeout_seconds: int
    ) -> tuple[bool, str]: ...

    def stop_all_motors(self) -> tuple[bool, str]: ...

    def request_periodic_battery_status(self, interval_microseconds: int) -> tuple[bool, str]: ...

    def get_battery_status(self) -> tuple[Union[tuple[float, float], None], str]: ...

    def get_voltage_thresholds(self) -> tuple[float, float]: ...

    def is_battery_monitoring_enabled(self) -> bool: ...

    def get_frame_info(self) -> tuple[int, int]: ...


class FlightControllerFilesProtocol(Protocol):
    """
    Protocol for flight controller file operations.

    Dependencies:
        Required at construction:
            - connection_manager: FlightControllerConnectionProtocol (to access master and info)
    """

    def upload_file(
        self, local_filename: str, remote_filename: str, progress_callback: Union[None, Callable[[int, int], None]]
    ) -> bool: ...

    def download_last_flight_log(
        self, local_filename: str, progress_callback: Union[None, Callable[[int, int], None]]
    ) -> bool: ...
