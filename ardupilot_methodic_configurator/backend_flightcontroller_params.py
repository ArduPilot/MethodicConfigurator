"""
Flight controller parameter management.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import debug as logging_debug
from logging import error as logging_error
from logging import info as logging_info
from logging import warning as logging_warning
from math import nan
from pathlib import Path
from time import sleep as time_sleep
from time import time as time_time
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

from pymavlink import mavutil

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller_connection import DEVICE_FC_PARAM_FROM_FILE
from ardupilot_methodic_configurator.backend_flightcontroller_factory_mavftp import create_mavftp
from ardupilot_methodic_configurator.data_model_flightcontroller_info import FlightControllerInfo
from ardupilot_methodic_configurator.data_model_par_dict import ParDict, validate_param_name

# Type hint for connection manager to avoid circular imports
if TYPE_CHECKING:
    from ardupilot_methodic_configurator.backend_flightcontroller_protocols import FlightControllerConnectionProtocol


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
    PARAM_SET_PROPAGATION_DELAY: float = 0.5
    FILE_SYNC_DELAY: float = 0.3
    PARAM_FETCH_POLL_DELAY: float = 0.01
    PARAM_RESET_TIMEOUT: float = 10.0
    MAVFTP_GETPARAMS_TIMEOUT: float = 40.0

    def __init__(
        self,
        connection_manager: Optional["FlightControllerConnectionProtocol"] = None,
        fc_parameters: Optional[dict[str, float]] = None,  # to simplify testing/mocking
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

    @property
    def master(self) -> Optional[mavutil.mavlink_connection]:  # pyright: ignore[reportGeneralTypeIssues]
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
        progress_callback: Union[None, Callable[[int, int], None]] = None,
        parameter_values_filename: Optional[Path] = None,
        parameter_defaults_filename: Optional[Path] = None,
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

        # Check if MAVFTP is supported
        if self.info.is_mavftp_supported:
            logging_info(_("MAVFTP is supported by the %s flight controller"), self.comport_device)

            param_dict, default_param_dict = self._download_params_via_mavftp(
                progress_callback, parameter_values_filename, parameter_defaults_filename
            )
            if param_dict:
                self.fc_parameters = param_dict
                return param_dict, default_param_dict

        logging_info(_("MAVFTP is not supported by the %s flight controller, fallback to MAVLink"), self.comport_device)
        param_dict = self._download_params_via_mavlink(progress_callback)
        self.fc_parameters = param_dict
        return param_dict, ParDict()

    def _download_params_via_mavlink(
        self, progress_callback: Union[None, Callable[[int, int], None]] = None
    ) -> dict[str, float]:
        """
        Requests all flight controller parameters via MAVLink PARAM_REQUEST_LIST.

        Gets parameters via PARAM_REQUEST_LIST and PARAM_VALUE messages

        Args:
            progress_callback: A callback function to report download progress

        Returns:
            dict[str, float]: A dictionary of flight controller parameters

        """
        logging_debug(_("Will fetch all parameters from the %s flight controller"), self.comport_device)

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
                param_id = message["param_id"]
                param_value = message["param_value"]
                parameters[param_id] = param_value
                logging_debug(_("Received parameter: %s = %s"), param_id, param_value)
                # Call the progress callback with the current progress
                if progress_callback:
                    progress_callback(len(parameters), m.param_count)
                if m.param_count == len(parameters):
                    logging_debug(
                        _("Fetched %d parameter values from the %s flight controller"), m.param_count, self.comport_device
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
        mavftp = create_mavftp(self.master)

        def get_params_progress_callback(completion: float) -> None:
            if progress_callback is not None and completion is not None:
                progress_callback(int(completion * 100), 100)

        complete_param_filename = str(parameter_values_filename) if parameter_values_filename else "complete.param"
        default_param_filename = str(parameter_defaults_filename) if parameter_defaults_filename else "00_default.param"
        mavftp.cmd_getparams([complete_param_filename, default_param_filename], progress_callback=get_params_progress_callback)
        # on slow links parameter download might take a long time
        ret = mavftp.process_ftp_reply("getparams", timeout=self.MAVFTP_GETPARAMS_TIMEOUT)
        pdict: dict[str, float] = {}
        defdict: ParDict = ParDict()

        # add a file sync operation to ensure the file is completely written
        time_sleep(self.FILE_SYNC_DELAY)
        if ret.error_code == 0:
            # load the parameters from the file
            par_dict = ParDict.from_file(complete_param_filename)
            pdict = {name: data.value for name, data in par_dict.items()}
            defdict = ParDict.from_file(default_param_filename)
        else:
            ret.display_message()

        if progress_callback is not None:
            progress_callback(100, 100)

        return pdict, defdict

    def set_param(self, param_name: str, param_value: float) -> tuple[bool, str]:
        """
        Set a parameter on the flight controller.

        Note: This method sends the parameter but does NOT wait for confirmation.
        This is an ArduPilot limitation - the parameter_set command does not return an ACK.

        Args:
            param_name: The name of the parameter to set
            param_value: The value to set the parameter to

        Returns:
            tuple[bool, str]: (True, "") if command sent successfully,
                             (False, error_message) if no connection available or invalid parameters

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
        # Note: We do NOT update fc_parameters here because:
        # 1. ArduPilot's param_set doesn't send confirmation (no ACK)
        # 2. The parameter should only be updated when read back from FC (via MAVFTP or fetch_param)
        # 3. This ensures fc_parameters always reflects the actual FC state
        return True, ""

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

    def fetch_param(self, param_name: str, timeout: int = 5) -> Optional[float]:
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
            param_msg: Any = self.master.recv_match(type="PARAM_VALUE", blocking=False)
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
