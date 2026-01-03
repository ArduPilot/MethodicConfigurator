"""
Flight controller command execution and status queries.

This file is part of ArduPilot Methodic Configurator. https://github.com/ArduPilot/MethodicConfigurator

SPDX-FileCopyrightText: 2024-2026 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
"""

from logging import debug as logging_debug
from logging import error as logging_error
from logging import info as logging_info
from time import sleep as time_sleep
from time import time as time_time
from typing import ClassVar, Optional, Union

from pymavlink import mavutil

from ardupilot_methodic_configurator import _
from ardupilot_methodic_configurator.backend_flightcontroller_business_logic import (
    calculate_voltage_thresholds,
    convert_battery_telemetry_units,
    get_frame_info,
    is_battery_monitoring_enabled,
)
from ardupilot_methodic_configurator.backend_flightcontroller_protocols import (
    FlightControllerConnectionProtocol,
    FlightControllerParamsProtocol,
    MavlinkConnection,
)


class FlightControllerCommands:
    """
    Handles MAVLink command execution and status queries.

    This class manages all command-related operations:
    - Motor testing (individual, all, sequence)
    - Battery status monitoring
    - Frame information retrieval
    - Command acknowledgment handling

    Note: Commands manager queries params_manager for parameter values
    rather than caching references, ensuring fresh data.
    """

    # Command timeout constants
    COMMAND_ACK_TIMEOUT: ClassVar[float] = 5.0
    COMMAND_ACK_TIMEOUT_BATTERY: ClassVar[float] = 0.8
    MOTOR_TEST_COMMAND_DELAY: ClassVar[float] = 0.01
    BATTERY_STATUS_TIMEOUT: ClassVar[float] = 1.5
    BATTERY_STATUS_CACHE_TIME: ClassVar[float] = 3.0
    BATTERY_STATUS_REQUEST_ATTEMPTS: ClassVar[int] = 3
    BATTERY_STATUS_REQUEST_DELAY: ClassVar[float] = 0.3
    BATTERY_STATUS_ACTIVATION_WAIT: ClassVar[float] = 1.0

    def __init__(
        self,
        params_manager: Optional[FlightControllerParamsProtocol] = None,
        connection_manager: Optional[FlightControllerConnectionProtocol] = None,
    ) -> None:
        """
        Initialize the command manager.

        Args:
            params_manager: Parameters manager to query for parameter values (recommended)
            connection_manager: Connection manager to get master from (recommended)

        """
        if params_manager is None:
            msg = "params_manager is required"
            raise ValueError(msg)
        if connection_manager is None:
            msg = "connection_manager is required"
            raise ValueError(msg)
        self._params_manager: FlightControllerParamsProtocol = params_manager
        self._connection_manager: FlightControllerConnectionProtocol = connection_manager
        self._last_battery_status: Optional[tuple[float, float]] = None
        self._last_battery_message_time: float = 0.0

    @property
    def master(self) -> Optional[MavlinkConnection]:
        """Get master connection - delegates to connection manager."""
        return self._connection_manager.master

    def send_command_and_wait_ack(  # pylint: disable=too-many-arguments,too-many-positional-arguments, too-many-locals
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
            self.master.mav.command_long_send(  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue]
                self.master.target_system,  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue]
                self.master.target_component,  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue]
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
                msg = self.master.recv_match(  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue]
                    type="COMMAND_ACK", blocking=False
                )
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
            logging_error(error_msg)
            return False, error_msg

        # MAV_CMD_PREFLIGHT_STORAGE command
        # https://mavlink.io/en/messages/common.html#MAV_CMD_PREFLIGHT_STORAGE
        # param1 = 2: Erase all parameters
        success, error_msg = self.send_command_and_wait_ack(
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
            # Clear local cache in params manager
            self._params_manager.fc_parameters.clear()
        else:
            error_msg = _("Parameter reset command failed: %(error)s") % {"error": error_msg}
            logging_error(error_msg)

        return success, error_msg

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
        success, error_msg = self.send_command_and_wait_ack(
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
            self.master.mav.command_long_send(  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue]
                self.master.target_system,  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue]
                self.master.target_component,  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue]
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
            time_sleep(self.MOTOR_TEST_COMMAND_DELAY)  # to let the FC parse each command individually

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
        success, error_msg = self.send_command_and_wait_ack(
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
        success, error_msg = self.send_command_and_wait_ack(
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

        last_error = ""
        request_succeeded = False
        for attempt in range(self.BATTERY_STATUS_REQUEST_ATTEMPTS):
            success, error_msg = self.send_command_and_wait_ack(
                mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
                param1=mavutil.mavlink.MAVLINK_MSG_ID_BATTERY_STATUS,  # message ID (BATTERY_STATUS)
                param2=interval_microseconds,  # interval in microseconds
                param3=0,
                param4=0,
                param5=0,
                param6=0,
                param7=0,
                timeout=self.COMMAND_ACK_TIMEOUT_BATTERY,
            )
            if success:
                request_succeeded = True
                logging_debug(
                    _("BATTERY_STATUS stream request attempt %(attempt)d confirmed"),
                    {"attempt": attempt + 1},
                )
            else:
                last_error = error_msg
                logging_debug(
                    _("BATTERY_STATUS stream request attempt %(attempt)d failed: %(error)s"),
                    {"attempt": attempt + 1, "error": error_msg},
                )
            time_sleep(self.BATTERY_STATUS_REQUEST_DELAY)

        if not request_succeeded:
            error_msg = _("Failed to request periodic battery status: %(error)s") % {"error": last_error}
            logging_debug(error_msg)
            return False, error_msg

        logging_debug(
            _("Periodic BATTERY_STATUS messages confirmed every %(interval)d microseconds"),
            {"interval": interval_microseconds},
        )
        time_sleep(self.BATTERY_STATUS_ACTIVATION_WAIT)
        return True, ""

    def get_battery_status(self) -> tuple[Union[tuple[float, float], None], str]:
        """
        Get current battery voltage and current.

        Returns:
            tuple[Union[tuple[float, float], None], str]: ((voltage, current), error_message) -
                                                         voltage and current in volts and amps,
                                                         or None if not available with error message

        """
        if not self._params_manager.fc_parameters or self.master is None:
            error_msg = _("No flight controller connection or parameters available")
            return None, error_msg

        # Check if battery monitoring is enabled
        if not self.is_battery_monitoring_enabled():
            error_msg = _("Battery monitoring is not enabled (BATT_MONITOR=0)")
            return None, error_msg

        try:
            # Try to get real telemetry data
            battery_status = self.master.recv_match(  # type: ignore[union-attr] # pyright: ignore[reportAttributeAccessIssue]
                type="BATTERY_STATUS", blocking=False, timeout=self.BATTERY_STATUS_TIMEOUT
            )
            if battery_status:
                # Convert from millivolts to volts, and centiamps to amps using pure business logic
                voltage, current = convert_battery_telemetry_units(
                    battery_status.voltages[0],
                    battery_status.current_battery,
                )
                self._last_battery_status = (voltage, current)
                self._last_battery_message_time = time_time()
                return (voltage, current), ""
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging_debug(_("Failed to get battery status from telemetry: %(error)s"), {"error": str(e)})

        if (
            self._last_battery_message_time
            and (time_time() - self._last_battery_message_time) < self.BATTERY_STATUS_CACHE_TIME
        ):
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
        return calculate_voltage_thresholds(self._params_manager.fc_parameters)

    def is_battery_monitoring_enabled(self) -> bool:
        """
        Check if battery monitoring is enabled.

        Returns:
            bool: True if BATT_MONITOR != 0, False otherwise

        """
        return is_battery_monitoring_enabled(self._params_manager.fc_parameters)

    def get_frame_info(self) -> tuple[int, int]:
        """
        Get frame class and frame type from flight controller parameters.

        Returns:
            tuple[int, int]: (frame_class, frame_type)

        """
        return get_frame_info(self._params_manager.fc_parameters)
