"""
Flight controller parameter management.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from collections import deque
from collections.abc import Callable
from logging import debug as logging_debug
from logging import error as logging_error
from logging import info as logging_info
from logging import warning as logging_warning
from math import nan
from pathlib import Path
from time import monotonic as time_monotonic
from time import sleep as time_sleep
from time import time as time_time
from typing import TYPE_CHECKING, Any, ClassVar, Optional

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller_connection import DEVICE_FC_PARAM_FROM_FILE
from ardupilot_methodic_configurator.backend_flightcontroller_factory_mavftp import create_mavftp
from ardupilot_methodic_configurator.backend_flightcontroller_factory_mavlink import BufferedMavlinkConnection
from ardupilot_methodic_configurator.backend_mavlink_param_error import (
    get_param_error_message,
    install_param_error_message,
)
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo
from ardupilot_methodic_configurator.data_model_par_dict import Par, ParDict, validate_param_name

# Type hint for connection manager to avoid circular imports
if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller_protocols import (
        FlightControllerConnectionProtocol,
        MavlinkConnection,
    )


class _ProgressReporter:  # pylint: disable=too-few-public-methods
    """Safely report progress and disable a callback after its first failure."""

    def __init__(self, callback: Callable[[int, int], None] | None) -> None:
        self.callback = callback

    def __call__(self, current: int, total: int) -> None:
        """Report progress without allowing callback failures to interrupt a transfer."""
        if self.callback is None:
            return
        try:
            self.callback(current, total)
        except Exception as error:  # pylint: disable=broad-exception-caught
            logging_warning(
                _("Parameter download progress update failed: %(error)s"),
                {"error": str(error)},
            )
            self.callback = None


class FlightControllerParams:
    """
    Manages flight controller parameter operations.

    This class handles all parameter-related operations:
    - Downloading parameters (via MAVLink or MAVFTP)
    - Setting individual parameters
    - Fetching individual parameters
    - Resetting all parameters to defaults
    """

    # Parameter operation timeout constants
    PARAM_FETCH_POLL_DELAY: float = 0.01
    # Give the flight controller and a normal telemetry link time to return an
    # error.  This is deliberately independent from the 10 ms polling cadence.
    PARAM_SET_PROPAGATION_DELAY: float = 0.1
    FILE_SYNC_DELAY: float = 0.3
    PARAM_RESET_TIMEOUT: float = 10.0
    MAVFTP_GETPARAMS_TIMEOUT: float = 40.0

    PARAM_ERROR_MESSAGES: ClassVar[dict[int, str]] = {
        1: _("Parameter does not exist"),
        2: _("Parameter value is out of range"),
        3: _("Permission denied while setting parameter"),
        4: _("Target component was not found"),
        5: _("Parameter is read-only"),
        6: _("Parameter type is not supported"),
        7: _("Parameter type does not match"),
        8: _("Parameter read failed"),
    }

    def __init__(
        self,
        connection_manager: Optional["FlightControllerConnectionProtocol"] = None,
        fc_parameters: dict[str, float] | None = None,  # to simplify testing/mocking
    ) -> None:
        """
        Initialize the parameter manager.

        Args:
            connection_manager: Connection manager to get master/info/comport from
            fc_parameters: Shared parameter dictionary (if None, creates new one)

        """
        if connection_manager is None:
            msg = "connection_manager is required"
            raise ValueError(msg)
        self._connection_manager: FlightControllerConnectionProtocol = connection_manager
        # Use provided fc_parameters dict or create new one
        self.fc_parameters: dict[str, float] = fc_parameters if fc_parameters is not None else {}
        # These queues hold only messages received during a bounded parameter
        # operation.  Do not silently discard a message: a later fetch/download
        # must be able to consume every preserved PARAM_VALUE.
        self._pending_messages: deque[object] = deque()

    @property
    def master(self) -> Optional["MavlinkConnection"]:
        """Get master connection."""
        return self._connection_manager.master

    @property
    def info(self) -> FlightControllerInfo:
        """Get flight controller info."""
        return self._connection_manager.info

    @property
    def comport_device(self) -> str:
        """Get comport device string."""
        return self._connection_manager.comport_device

    def download_params(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
        parameter_values_filename: Path | None = None,
        parameter_defaults_filename: Path | None = None,
    ) -> tuple[dict[str, float], ParDict]:
        """
        Requests all flight controller parameters from a MAVLink connection.

        Args:
            progress_callback: A callback function to report download progress
            parameter_values_filename: The filename to save the parameter values
            parameter_defaults_filename: The filename to save the parameter defaults

        Returns:
            tuple[dict[str, float], ParDict]: (parameter_values, default_parameters)
                parameter_values is a dictionary of parameter name to value
                default_parameters is a ParDict of default parameter values

        """
        if self.master is None and self.comport_device == DEVICE_FC_PARAM_FROM_FILE:
            filename = "params.param"
            logging_warning(_("Testing active, will load all parameters from the %s file"), filename)
            par_dict_with_comments = ParDict.from_file(filename)
            param_dict = {k: v.value for k, v in par_dict_with_comments.items()}
            self.fc_parameters = param_dict
            return param_dict, ParDict()

        if self.master is None:
            return {}, ParDict()

        progress_reporter = _ProgressReporter(progress_callback)

        # Check if MAVFTP is supported
        if self.info.is_mavftp_supported:
            logging_info(_("MAVFTP is supported by the %s flight controller"), self.comport_device)

            param_dict, default_param_dict = self._download_params_via_mavftp(
                progress_reporter, parameter_values_filename, parameter_defaults_filename
            )
            if param_dict:
                self.fc_parameters = param_dict
                return param_dict, default_param_dict
            logging_info(_("MAVFTP parameter download failed on the %s, fallback to MAVLink"), self.comport_device)
        else:
            logging_info(_("MAVFTP is not supported by the %s flight controller, fallback to MAVLink"), self.comport_device)
        param_dict, download_complete = self._download_params_via_mavlink(progress_reporter)
        if not download_complete:
            logging_error(_("Incomplete parameter download from the %s flight controller"), self.comport_device)
            return {}, ParDict()
        self.fc_parameters = param_dict
        if parameter_values_filename is not None and param_dict:
            ParDict({name: Par(value) for name, value in param_dict.items()}).export_to_param(str(parameter_values_filename))
        return param_dict, ParDict()

    def _download_params_via_mavlink(
        self, progress_callback: Callable[[int, int], None] | None = None
    ) -> tuple[dict[str, float], bool]:
        """
        Requests all flight controller parameters via MAVLink PARAM_REQUEST_LIST.

        Gets parameters via PARAM_REQUEST_LIST and PARAM_VALUE messages

        Args:
            progress_callback: A callback function to report download progress

        Returns:
            A tuple containing the parameter dictionary and whether all advertised
            parameters were received.

        """
        progress_reporter = (
            progress_callback if isinstance(progress_callback, _ProgressReporter) else _ProgressReporter(progress_callback)
        )
        logging_debug(_("Will fetch all parameters from the %s flight controller"), self.comport_device)

        # Dictionary to store parameters
        parameters: dict[str, float] = {}

        # Request all parameters
        if self.master is None:
            return parameters, False

        self.master.mav.param_request_list_send(self.master.target_system, self.master.target_component)

        try:
            # Loop to receive all parameters
            while True:
                m = self._pop_pending_message("PARAM_VALUE")
                if m is None:
                    m = self.master.recv_match(type="PARAM_VALUE", blocking=True, timeout=10)
                if m is None:
                    return parameters, False
                message = m.to_dict()
                param_id = message["param_id"]
                param_value = message["param_value"]
                parameters[param_id] = param_value
                logging_debug(_("Received parameter: %s = %s"), param_id, param_value)
                progress_reporter(len(parameters), m.param_count)
                if m.param_count == len(parameters):
                    logging_debug(
                        _("Fetched %d parameter values from the %s flight controller"), m.param_count, self.comport_device
                    )
                    return parameters, True
        except Exception as error:  # pylint: disable=broad-except
            logging_error(_("Error: %s"), error)
            return parameters, False

    def _download_params_via_mavftp(
        self,
        progress_callback: Callable[[int, int], None] | None = None,
        parameter_values_filename: Path | None = None,
        parameter_defaults_filename: Path | None = None,
    ) -> tuple[dict[str, float], ParDict]:
        """
        Requests all flight controller parameters via MAVFTP protocol.

        Gets parameters via MAVFTP protocol, which is faster than MAVLink for parameter downloads.

        Args:
            progress_callback: A callback function to report download progress
            parameter_values_filename: The filename to save the parameter values
            parameter_defaults_filename: The filename to save the parameter defaults

        Returns:
            tuple[dict[str, float], ParDict]: (parameter_values, default_parameters)

        """
        if self.master is None:
            return {}, ParDict()
        progress_reporter = (
            progress_callback if isinstance(progress_callback, _ProgressReporter) else _ProgressReporter(progress_callback)
        )
        try:
            mavftp = create_mavftp(self.master)

            def get_params_progress_callback(completion: float) -> None:
                if progress_callback is not None and completion is not None:
                    progress_reporter(int(completion * 100), 100)

            complete_param_filename = str(parameter_values_filename) if parameter_values_filename else "complete.param"
            default_param_filename = str(parameter_defaults_filename) if parameter_defaults_filename else "00_default.param"
            mavftp.cmd_getparams(
                [complete_param_filename, default_param_filename], progress_callback=get_params_progress_callback
            )
            # On slow links parameter download might take a long time.
            ret = mavftp.process_ftp_reply("getparams", timeout=self.MAVFTP_GETPARAMS_TIMEOUT)
            pdict: dict[str, float] = {}
            defdict = ParDict()

            # Add a file sync operation to ensure the file is completely written.
            time_sleep(self.FILE_SYNC_DELAY)
            if ret.error_code == 0:
                par_dict = ParDict.from_file(complete_param_filename)
                pdict = {name: data.value for name, data in par_dict.items()}
                defdict = ParDict.from_file(default_param_filename)
            else:
                ret.display_message()

            if pdict:
                progress_reporter(100, 100)
            return pdict, defdict
        except Exception as error:  # pylint: disable=broad-exception-caught
            logging_warning(
                _("MAVFTP parameter download failed; falling back to MAVLink: %(error)s"),
                {"error": str(error)},
                exc_info=True,
            )
            return {}, ParDict()

    def set_param(self, param_name: str, param_value: float) -> tuple[bool, str]:
        """
        Set a parameter on the flight controller.

        Newer ArduPilot firmware may reply with MAVLink-2 ``PARAM_ERROR`` when it
        rejects a parameter write. Older firmware does not send an acknowledgement,
        so expiration of the short response window is treated as an unknown-but-sent
        result. Callers that require positive confirmation must still read the
        parameter back with :meth:`fetch_param`.

        Args:
            param_name: The name of the parameter to set
            param_value: The value to set the parameter to

        Returns:
            tuple[bool, str]: ``(True, "")`` when the command was sent without an
                              observed rejection; ``(False, error_message)`` on a
                              local validation failure, missing connection, or a
                              matching ``PARAM_ERROR`` response.

        """
        if self.master is None:
            return False, _("No flight controller connection available")

        # Validate parameter name using ArduPilot standards
        is_valid_name, name_error = validate_param_name(param_name)
        if not is_valid_name:
            logging_error(name_error)
            return False, name_error

        # Validate parameter value
        if not isinstance(param_value, (int, float)):
            error_msg = _("Invalid parameter value type: %s (expected numeric)") % type(param_value).__name__
            logging_error(error_msg)
            return False, error_msg

        self.master.param_set_send(param_name, param_value)
        error_code = self._wait_for_param_error(param_name)
        if error_code is not None:
            error_msg = self.PARAM_ERROR_MESSAGES.get(error_code, _("Flight controller rejected parameter write"))
            error_msg = _("Failed to set %(name)s: %(error)s") % {"name": param_name, "error": error_msg}
            logging_error(error_msg)
            return False, error_msg

        # Note: We do NOT update fc_parameters here because:
        # 1. Successful PARAM_SET messages do not have a universal acknowledgement.
        # 2. The parameter should only be updated when read back from FC (via MAVFTP or fetch_param).
        # 3. This ensures fc_parameters always reflects the actual FC state
        return True, ""

    def _wait_for_param_error(self, param_name: str) -> int | None:
        """
        Wait briefly for a PARAM_ERROR response to a just-sent PARAM_SET.

        A timeout is successful from this method's perspective because legacy
        ArduPilot versions do not emit a response for successful or rejected writes.

        """
        if self.master is None:
            return None

        if not self._connection_manager.info.fw_supports_param_set_ack:
            return None

        install_param_error_message()
        start_time = time_monotonic()
        while time_monotonic() - start_time < self.PARAM_SET_PROPAGATION_DELAY:
            remaining = self.PARAM_SET_PROPAGATION_DELAY - (time_monotonic() - start_time)
            message = self._receive_next_message(timeout=remaining)
            if message is not None:
                message_type = getattr(message, "get_type", lambda: None)()
                if message_type not in (None, "PARAM_ERROR"):
                    # recv_match(type=...) discards non-matching MAVLink messages.
                    # Read unfiltered messages instead and retain them for the
                    # parameter operations that may be waiting for them.
                    self._pending_messages.append(message)
                    continue
                error_code = get_param_error_message(message, param_name)
                if error_code is not None:
                    # MAV_PARAM_ERROR_NO_ERROR is an acknowledgement, not a rejection.
                    return error_code or None
                # PARAM_ERROR has no request sequence or value.  A non-matching
                # response cannot safely be assigned to a future write (including
                # a same-name retry), so it is deliberately not buffered.
                logging_debug("Discarding unmatched PARAM_ERROR while setting %s", param_name)
                continue
            time_sleep(self.PARAM_FETCH_POLL_DELAY)
        return None

    def _receive_next_message(self, timeout: float | None = None) -> object | None:
        """Receive one unfiltered MAVLink message without dropping other types."""
        if self.master is None:
            return None

        # The production connection adapter filters without dropping unrelated
        # messages. Keep the recv_msg fallback for lightweight test doubles.
        if isinstance(self.master, BufferedMavlinkConnection):
            return self.master.recv_match(type="PARAM_ERROR", blocking=True, timeout=timeout)  # type: ignore[union-attr]
        return self.master.recv_msg()  # type: ignore[union-attr]

    def _pop_pending_message(self, message_type: str, param_name: str = "") -> object | None:
        """Remove and return a buffered message of the requested parameter type."""
        for message in list(self._pending_messages):
            if getattr(message, "get_type", lambda: None)() != message_type:
                continue
            if not param_name:
                self._pending_messages.remove(message)
                return message
            received_name = getattr(message, "param_id", "")
            if isinstance(received_name, bytes):
                received_name = received_name.decode("ascii", errors="replace")
            if isinstance(received_name, str) and received_name.rstrip("\x00") == param_name:
                self._pending_messages.remove(message)
                return message
        return None

    def get_param(self, param_name: str, default: float = nan) -> float:
        """
        Get a parameter value from the local cache.

        Args:
            param_name: The name of the parameter to get
            default: Default value if parameter not found

        Returns:
            float: The parameter value from cache, or default if not found

        """
        return self.fc_parameters.get(param_name, default)

    def fetch_param(self, param_name: str, timeout: int = 5) -> float | None:
        """
        Fetch a parameter from the flight controller using MAVLink PARAM_REQUEST_READ message.

        Args:
            param_name: The name of the parameter to fetch
            timeout: Timeout in seconds to wait for the response. Default is 5

        Returns:
            float: The value of the parameter

        """
        if self.master is None:
            return None

        # Validate parameter name using ArduPilot standards
        is_valid_name, name_error = validate_param_name(param_name)
        if not is_valid_name:
            logging_error(name_error)
            raise IndexError(name_error)

        if timeout <= 0:
            msg = _("Timeout for parameter %s is non-positive, skipping request") % param_name
            logging_error(msg)
            raise ValueError(msg)

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
            param_msg: Any = self._pop_pending_message("PARAM_VALUE", param_name)
            if param_msg is None:
                param_msg = self.master.recv_match(type="PARAM_VALUE", blocking=False)
            if param_msg is not None:
                # Check if this is the parameter we requested
                received_param_name = param_msg.param_id.rstrip("\x00")
                if received_param_name == param_name:
                    logging_debug(_("Received parameter: %s = %s"), param_name, param_msg.param_value)
                    value = float(param_msg.param_value)
                    # Update local cache
                    self.fc_parameters[param_name] = value
                    return value
            time_sleep(self.PARAM_FETCH_POLL_DELAY)  # Small sleep to prevent busy waiting

        raise TimeoutError(_("Timeout waiting for parameter %s") % param_name)

    def clear_parameters(self) -> None:
        """
        Clear all cached parameters.

        This should be called when disconnecting from the flight controller
        to ensure stale parameter data is not retained.
        """
        self.fc_parameters.clear()
